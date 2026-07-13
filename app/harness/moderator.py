import logging
from typing import Any, List, Optional, Tuple  # noqa: UP035

from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.workflow import node
from pydantic import BaseModel, Field

from app.config import settings
from app.types import DebateRound, PillarScores
from app.utils import parse_node_input

logger = logging.getLogger(__name__)


class AgreementMatrix(BaseModel):
    """Structured matrix of agreed baseline points vs active contentions across debate turns."""
    agreed_points: List[str] = Field(default_factory=list, description="Architectural points mutually agreed upon")  # noqa: UP006
    active_contentions: list[str] = Field(default_factory=list, description="Unresolved architectural trade-offs or disputes")
    summary_text: str = Field(default="", description="Markdown summary of the agreement state")


class AgreementMatrixExtraction(BaseModel):
    """Pydantic schema for structured lightweight semantic extraction."""
    agreed_points: List[str] = Field(default_factory=list, description="Architectural agreements extracted from debate history")  # noqa: UP006
    active_contentions: List[str] = Field(default_factory=list, description="Architectural trade-offs or contentions")  # noqa: UP006
    extracted_facts: List[str] = Field(default_factory=list, description="Mutually verified factual architectural statements")  # noqa: UP006


class RoundManager:
    """Enforces debate round bounds to prevent infinite loops and token bleeding."""

    def __init__(self, max_rounds: int = 3):
        self.max_rounds = max_rounds

    def should_terminate_debate(self, current_round: int) -> bool:
        """Returns True if the debate has reached or exceeded the maximum permitted rounds."""
        return current_round >= self.max_rounds


class ContextSummarizer:
    """
    Condenses previous debate rounds into an AgreementMatrix so agents do not repeat arguments.
    Supports deterministic heuristic synthesis as well as lightweight semantic structured model extraction.
    """

    @staticmethod
    def build_agreement_matrix(rounds_history: List[DebateRound]) -> AgreementMatrix:  # noqa: UP006
        """Deterministic heuristic fallback that synthesizes an AgreementMatrix from historical DebateRound objects."""
        agreed: List[str] = []  # noqa: UP006
        contentions: List[str] = []  # noqa: UP006

        for rnd in rounds_history:
            prop_lines = [l.strip() for l in rnd.proposal_draft.splitlines() if l.strip().startswith("-") or l.strip().startswith("*")]
            crit_lines = [l.strip() for l in rnd.critique.splitlines() if l.strip().startswith("-") or l.strip().startswith("*")]

            for l in prop_lines[:3]:
                if l not in agreed:
                    agreed.append(l.lstrip("-* "))
            for l in crit_lines[:3]:
                if any(kw in l.lower() for kw in ("risk", "latency", "bottleneck", "contention", "tradeoff")):
                    if l not in contentions:
                        contentions.append(l.lstrip("-* "))

        summary_parts = ["### Points of Architectural Agreement:"]
        summary_parts.extend(f"- {p}" for p in agreed or ["Baseline concept established"])
        summary_parts.append("\n### Active Architectural Contentions:")
        summary_parts.extend(f"- {c}" for c in contentions or ["No critical blocking contentions reported"])

        return AgreementMatrix(
            agreed_points=agreed,
            active_contentions=contentions,
            summary_text="\n".join(summary_parts),
        )

    @classmethod
    def extract_semantic_agreement(cls, rounds_history: List[DebateRound]) -> AgreementMatrix:
        """
        Uses a lightweight Gemini Flash call with structured output schema (AgreementMatrixExtraction)
        to extract semantic architectural agreements and contentions. Falls back to deterministic heuristic if mock_mode.
        """
        if settings.mock_mode or not rounds_history:
            return cls.build_agreement_matrix(rounds_history)

        try:
            client = settings.get_genai_client()
            history_summary = "\n\n".join(
                f"Round {rnd.round_number}:\nProposal: {rnd.proposal_draft[:600]}\nCritique: {rnd.critique[:600]}"
                for rnd in rounds_history
            )
            prompt = (
                "Analyze the following architectural debate history and extract key architectural agreements, "
                "active technical contentions, and verified architectural facts:\n\n"
                f"{history_summary}"
            )

            response = client.models.generate_content(
                model=settings.auditor_model_id,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": AgreementMatrixExtraction,
                    "temperature": 0.1,
                },
            )

            extraction = AgreementMatrixExtraction.model_validate_json(response.text)
            summary_parts = ["### Points of Architectural Agreement:"]
            summary_parts.extend(f"- {p}" for p in extraction.agreed_points or ["Baseline concept established"])
            summary_parts.append("\n### Active Architectural Contentions:")
            summary_parts.extend(f"- {c}" for c in extraction.active_contentions or ["No critical blocking contentions reported"])

            return AgreementMatrix(
                agreed_points=extraction.agreed_points,
                active_contentions=extraction.active_contentions,
                summary_text="\n".join(summary_parts),
            )
        except Exception as e:
            logger.warning(f"Semantic agreement extraction failed ({e}); falling back to deterministic heuristic.")
            return cls.build_agreement_matrix(rounds_history)


# --- HARNESS DETERMINISTIC ROUTING CONTROL PREDICATES ---

def should_exit_grill(
    ctx: Context,
    user_answer: str = "",
    question_count: int = 0,
    max_questions: int = 3,
    model_output: str = "",
) -> bool:
    """Deterministic routing predicate for the grill phase."""
    if ctx.state.get("grill_completed", False) or ctx.state.get("current_round", 1) > 1:
        return True

    clean_user_answer = user_answer.strip().upper()
    if clean_user_answer in {"SKIP_INTERVIEW", "READY", "SKIP"}:
        return True

    if question_count >= max_questions:
        return True

    clean_model_output = model_output.strip().upper()
    if clean_model_output == "READY" or clean_model_output.startswith("READY"):
        return True

    return False


def should_synthesize_or_continue(
    scores: PillarScores | None = None,
    current_round: int = 1,
    max_rounds: int = 3,
    gate_threshold: float = 0.85,
    user_choice: str = "",
) -> Tuple[bool, str]:
    """Deterministic routing decision for evaluate_and_score_node."""
    clean_choice = user_choice.strip().upper()
    if clean_choice == "SYNTHESIZE":
        return True, "synthesize"
    if clean_choice == "CONTINUE" or (clean_choice and clean_choice != "SYNTHESIZE"):
        return False, "continue"

    if scores is not None:
        consensus = scores.meets_threshold(gate_threshold)
        if consensus or current_round >= max_rounds:
            return True, "synthesize"

    return False, "review"

# --- HARNESS ENTRYPOINT NODE ---

@node
def initialize_debate(ctx: Context, node_input: Any) -> Event:
    """Harness Node 1: Receives user software concept and boots up deterministic session state."""
    node_input = parse_node_input(node_input)

    if isinstance(node_input, dict):
        project_id = node_input.get("project_id") or ctx.state.get("project_id", "default_proj")
        concept = node_input.get("concept") or ctx.state.get("concept", "")
        caveman_mode = node_input.get("caveman_mode", ctx.state.get("caveman_mode", True))
        
        if "grill_history" in node_input and node_input["grill_history"]:
            ctx.state["grill_history"] = node_input["grill_history"]
        if "grill_question_count" in node_input:
            ctx.state["grill_question_count"] = node_input["grill_question_count"]
        if "grill_completed" in node_input:
            ctx.state["grill_completed"] = node_input["grill_completed"]
        if "grill_interaction_id" in node_input and node_input["grill_interaction_id"]:
            ctx.state["grill_interaction_id"] = node_input["grill_interaction_id"]
    else:
        project_id = ctx.state.get("project_id", "default_proj")
        concept = str(node_input) if node_input else ctx.state.get("concept", "")
        caveman_mode = ctx.state.get("caveman_mode", True)

    ctx.state["project_id"] = project_id
    if concept and str(concept).strip() not in {"", "None"}:
        ctx.state["concept"] = concept
    else:
        concept = ctx.state.get("concept", "A new software project")

    ctx.state["caveman_mode"] = caveman_mode
    ctx.state.setdefault("current_round", 1)
    ctx.state.setdefault("max_rounds", 3)
    ctx.state.setdefault("rounds_history", [])
    ctx.state.setdefault("grill_history", [])

    state_dict = ctx.state.to_dict() if hasattr(ctx.state, "to_dict") else dict(ctx.state)

    # Check explicit resume inputs first
    if isinstance(node_input, dict) and "judge_review" in node_input:
        return Event(output=node_input, route="review", custom_metadata={"state": state_dict})
    elif isinstance(node_input, dict) and "grill_question" in node_input:
        return Event(output=node_input, route="grill", custom_metadata={"state": state_dict})

    # If grilling has completed or debate rounds already exist, route to 'ready'
    if ctx.state.get("grill_completed", False) or len(ctx.state.get("rounds_history", [])) > 0:
        return Event(output=ctx.state.get("concept", concept), route="ready", custom_metadata={"state": state_dict})

    from app.harness.tracing import DebateTracer
    DebateTracer.record_span(
        ctx=ctx,
        span_name="SESSION_START",
        agent_role="Moderator",
        metadata={"concept": concept, "caveman_mode": caveman_mode},
    )

    return Event(output=node_input, route="grill", custom_metadata={"state": state_dict})


def mark_requirements_complete(
    ctx: Context,
    preferred_tech_stack: list[str] = None,
    cloud_provider: str = None,
    architectural_pattern: str = None,
    target_rps: int = None,
    budget_tier: str = None,
    compliance_frameworks: list[str] = None,
    core_use_cases: list[str] = None,
) -> dict:
    """Readiness gate function to explicitly lock Phase 1 project requirements into DebateState."""
    from app.types import RequirementsSchema
    req = RequirementsSchema(
        preferred_tech_stack=preferred_tech_stack or [],
        cloud_provider=cloud_provider,
        architectural_pattern=architectural_pattern,
        target_rps=target_rps,
        budget_tier=budget_tier,
        compliance_frameworks=compliance_frameworks or [],
        core_use_cases=core_use_cases or [ctx.state.get("concept", "")],
    )
    ctx.state["requirements"] = req.model_dump()
    ctx.state["grill_completed"] = True
    logger.info(f"Locked RequirementsSchema for project {ctx.state.get('project_id')}")

    from app.harness.tracing import DebateTracer
    DebateTracer.record_span(
        ctx=ctx,
        span_name="REQUIREMENTS_LOCKED",
        agent_role="Moderator",
        metadata={"tech_stack": req.preferred_tech_stack, "cloud": req.cloud_provider, "pattern": req.architectural_pattern},
    )
def extract_requirements_from_grilling(concept: str, grill_history: list) -> dict:
    """Extract structured Phase 1 requirements from project concept and interview history."""
    from app.types import RequirementsSchema
    tech_stack = []
    cloud = None
    pattern = None
    compliance = []
    use_cases = [concept]

    text_corpus = concept + " " + " ".join(str(item.get("content", "")) for item in grill_history if isinstance(item, dict))
    text_lower = text_corpus.lower()

    for tech in ["python", "fastapi", "react", "next.js", "typescript", "node.js", "go", "postgres", "redis", "mongodb", "dynamodb", "spanner", "kafka", "docker", "kubernetes"]:
        if tech in text_lower:
            tech_stack.append(tech)

    for cp, display in [("aws", "AWS"), ("gcp", "GCP"), ("google cloud", "GCP"), ("azure", "Azure")]:
        if cp in text_lower:
            cloud = display
            break

    for pat, display in [("microservice", "Microservices"), ("event sourc", "Event Sourcing"), ("serverless", "Serverless"), ("clean arch", "Clean Architecture"), ("monolith", "Modular Monolith")]:
        if pat in text_lower:
            pattern = display
            break

    for comp in ["soc2", "gdpr", "hipaa", "pci-dss", "iso27001"]:
        if comp in text_lower:
            compliance.append(comp.upper())

    return RequirementsSchema(
        preferred_tech_stack=tech_stack or ["Python / FastAPI", "TypeScript / React"],
        cloud_provider=cloud or "Multi-Cloud / GCP Preferred",
        architectural_pattern=pattern or "Clean Architecture (Event-Driven)",
        target_rps=1000 if ("scale" in text_lower or "high throughput" in text_lower) else 250,
        budget_tier="High Availability Enterprise Tier" if ("ha" in text_lower or "enterprise" in text_lower) else "Standard Production Tier",
        compliance_frameworks=compliance or ["Standard Security Best Practices"],
        core_use_cases=use_cases
    ).model_dump()


@node
async def grill_node(ctx: Context, node_input: Any) -> Event:
    """
    Harness Node 2: Interactive Grilling Phase.
    Repeatedly interviews the user to resolve design dependencies until ready.
    Uses RequestInput to pause execution and prompt for user clarification.
    """
    node_input = parse_node_input(node_input)
    client = settings.get_genai_client()
    project_id = ctx.state.get("project_id", "default_proj")
    concept = ctx.state.get("concept")
    if isinstance(node_input, dict) and node_input.get("concept") and str(node_input.get("concept")).strip() not in {"", "None"}:
        concept = node_input["concept"]
        ctx.state["concept"] = concept
    if not concept or str(concept).strip() in {"", "None"}:
        concept = "A new software project"
    question_count = ctx.state.get("grill_question_count", 0)
    max_questions = ctx.state.get("max_grill_questions", 3)
    previous_interaction_id = ctx.state.get("grill_interaction_id")

    grill_history = ctx.state.get("grill_history", [])

    user_answer = ""
    if isinstance(node_input, dict) and "grill_question" in node_input:
        user_answer = str(node_input["grill_question"])
    elif isinstance(node_input, str):
        user_answer = node_input

    if user_answer:
        question_count += 1
        ctx.state["grill_question_count"] = question_count
        grill_history.append({"role": "user", "content": user_answer})
        ctx.state["grill_history"] = grill_history

    if should_exit_grill(ctx, user_answer=user_answer, question_count=question_count, max_questions=max_questions):
        if user_answer.strip().upper() in {"SKIP_INTERVIEW", "SKIP"}:
            grill_history.append({"role": "assistant", "content": "Interview manually skipped. Proceeding to architectural debate."})
            ctx.state["grill_history"] = grill_history
        elif question_count >= max_questions:
            grill_history.append({"role": "assistant", "content": "I have all the context I need. Proceeding to architectural debate."})
            ctx.state["grill_history"] = grill_history
        ctx.state["grill_completed"] = True
        ctx.state["requirements"] = extract_requirements_from_grilling(concept, grill_history)
        state_dict = ctx.state.to_dict() if hasattr(ctx.state, "to_dict") else dict(ctx.state)
        yield Event(output=concept, route="ready", custom_metadata={"state": state_dict})
        return

    qa_history_lines = []
    q_idx = 1
    for item in grill_history:
        role = item.get("role", "")
        content = str(item.get("content", "")).strip()
        if role == "assistant":
            qa_history_lines.append(f"Architect (Question {q_idx}): {content}")
            q_idx += 1
        elif role == "user":
            qa_history_lines.append(f"User Answer: {content}\n")
    qa_history_text = "\n".join(qa_history_lines)

    next_q_num = question_count + 1
    prompt = f"""You are the Lead Performance Architect preparing to design: "{concept}".
Your goal is to grill the user to resolve critical architectural design dependencies.
Interview him relentlessly about every aspect of this project until you reach a shared understanding.
Walk down each branch of the design tree, resolving dependencies between decisions one-by-one.
"""
    if qa_history_text:
        prompt += f"""
=== PAST INTERVIEW HISTORY (DO NOT REPEAT PREVIOUS QUESTIONS) ===
{qa_history_text}
=================================================================
IMPORTANT INTERVIEW RULE: Look closely at the PAST INTERVIEW HISTORY above. DO NOT re-ask or rephrase any question that has already been asked and answered!
"""

    prompt += f"""
Latest User Input: "{user_answer if user_answer else 'No answer yet - starting interview'}"

If you fully understand the requirements and have enough context to start proposing the architecture, reply exactly with: READY
Otherwise, ask EXACTLY ONE focused, clarifying question that advances the architectural design.
Start your question clearly with "Question {next_q_num}:" and provide your recommended answer below it.
You have {max_questions - question_count} questions remaining.
"""

    if settings.mock_mode:
        if question_count == 0:
            text = f"[MOCK MODE] Welcome! I am the Lead Performance Architect preparing to design: '{concept}'. What is your target peak concurrent user load and expected latency SLA?"
        elif question_count == 1:
            text = "[MOCK MODE] Got it! What primary database topology and multi-region failover strategy do you prefer for this workload?"
        else:
            text = "READY"
    else:
        try:
            response = await client.aio.interactions.create(
                model=settings.grill_model_id,
                input=prompt,
                previous_interaction_id=previous_interaction_id
            )

            if hasattr(response, "id") and response.id:
                ctx.state["grill_interaction_id"] = response.id

            text = response.steps[-1].content[0].text.strip()
        except Exception as e:
            logger.warning(f"Interactions failed in grill_node, falling back to generate_content: {e}")
            fallback_res = await client.aio.models.generate_content(
                model=settings.grill_model_id,
                contents=prompt
            )
            text = fallback_res.text.strip()

    grill_history.append({"role": "assistant", "content": text})
    ctx.state["grill_history"] = grill_history

    state_dict = ctx.state.to_dict() if hasattr(ctx.state, "to_dict") else dict(ctx.state)
    if should_exit_grill(ctx, question_count=question_count, max_questions=max_questions, model_output=text):
        ctx.state["grill_completed"] = True
        ctx.state["requirements"] = extract_requirements_from_grilling(concept, grill_history)
        state_dict = ctx.state.to_dict() if hasattr(ctx.state, "to_dict") else dict(ctx.state)
        yield Event(output=concept, route="ready", custom_metadata={"state": state_dict})
        return

    from google.genai import types
    yield Event(
        content=types.Content(role="model", parts=[types.Part.from_text(text=text)]),
        custom_metadata={"state": state_dict}
    )

    yield RequestInput(
        payload={"name": "grill_question"},
        message=text
    )

    yield Event(output="Waiting for user", route="ask_user", custom_metadata={"state": state_dict})
    return
