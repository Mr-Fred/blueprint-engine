import os
import json
import logging
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

from google.adk.workflow import Workflow, node, JoinNode, START, RetryConfig
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.apps import App, ResumabilityConfig

from app.types import DebateState, DebateRound, PillarScores
from app.utils import FilesystemJail
from app.config import settings

# Import shared state registries to avoid circular dependencies
from app.shared_state import ACTIVE_DIRECTIVES, FORCE_SYNTHESIS_FLAGS

# Import modular agent nodes
from app.agents.performance.agent import performance_agent_node
from app.agents.security.agent import security_agent_node
from app.agents.sre.agent import sre_agent_node
from app.agents.performance.agent import grill_node

# Initialize Google Gen AI Client
def get_genai_client() -> genai.Client:
    # ADK uses Vertex AI by default, falling back to Gemini API
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() in ["true", "1"]
    location = settings.location if use_vertex else None
    return genai.Client(enterprise=use_vertex, project=settings.project_id, location=location)

@node
def initialize_debate(ctx: Context, node_input: Any) -> Event:
    """Node 1: Receives the user's software concept and boots up the baseline state."""
    if isinstance(node_input, str):
        try:
            parsed = json.loads(node_input)
            if isinstance(parsed, dict):
                node_input = parsed
        except Exception:
            pass

    if isinstance(node_input, dict):
        project_id = node_input.get("project_id", "default_proj")
        concept = node_input.get("concept", "")
    else:
        project_id = "default_proj"
        concept = str(node_input)
    
    # Check if we are resuming an existing restored state
    if ctx.state.get("current_round", 0) > 0:
        return Event(output=ctx.state.get("concept"), custom_metadata={"state": ctx.state.to_dict()})
    
    # Store initial concept and project_id in the workflow state
    ctx.state["project_id"] = project_id
    ctx.state["concept"] = concept
    ctx.state["current_round"] = 1
    ctx.state["rounds_history"] = []
    ctx.state["consensus_achieved"] = False
    
    return Event(output=concept, custom_metadata={"state": ctx.state.to_dict()})

# Join Node to combine Security and DevOps critiques
join_critiques = JoinNode(name="merge_critiques")

# Helper schema for structured score evaluation
class ScoreResult(BaseModel):
    scores: PillarScores = Field(..., description="Scores for the 6 pillars")
    evaluation_summary: str = Field(..., description="Detailed summary explaining the scores")

@node
async def evaluate_and_score_node(ctx: Context, node_input: dict) -> Event:
    """Node 4: Evaluates proposal and critiques, scores them on the 6 pillars, and routes."""
    
    # Check if we are resuming from a Human-in-the-Loop review pause
    if ctx.user_content and ctx.user_content.role == "user" and ctx.user_content.parts:
        try:
            import json
            payload = json.loads(ctx.user_content.parts[0].text)
            if isinstance(payload, dict):
                node_input = payload
        except Exception:
            pass

    if isinstance(node_input, dict) and "judge_review" in node_input:
        user_choice = str(node_input["judge_review"]).strip()
        if user_choice.upper() == "SYNTHESIZE":
            ctx.state["consensus_achieved"] = True
            yield Event(output=ctx.state.to_dict(), route="synthesize", custom_metadata={"state": ctx.state.to_dict()})
            return
        elif user_choice.upper() == "CONTINUE" or not user_choice:
            pass # Just continue the loop normally
        else:
            ctx.state["latest_judge_directive"] = user_choice
            
        proposal = ctx.state.get("latest_proposal", "")
        ctx.state["temp:latest_proposal"] = proposal
        yield Event(output=proposal, route="continue", custom_metadata={"state": ctx.state.to_dict()})
        return

    client = get_genai_client()
    
    # Extract parallel node outputs merged by JoinNode
    security_critique = node_input.get("security_agent_node", "")
    sre_critique = node_input.get("sre_agent_node", "")
    
    proposal = ctx.state.get("latest_proposal", "")
    if not proposal:
        proposal = "N/A"
        
    combined_critiques = f"--- SECURITY AUDIT ---\n{security_critique}\n\n--- SRE CRITIQUE ---\n{sre_critique}"

    prompt = f"""
    You are the Independent Master Architect Judge.
    Evaluate the following proposed design against its security and SRE critiques.
    
    Proposed Design:
    {proposal}
    
    Critiques & Audits:
    {combined_critiques}
    
    Assign a score between 0.0 (failing/flawed) and 1.0 (perfectly ready) for the 6 software quality pillars.
    """

    try:
        response = await client.aio.interactions.create(
            model=settings.model_id,
            input=prompt,
            response_format=ScoreResult.model_json_schema()
        )
        if response.steps and response.steps[-1].content:
            text_content = response.steps[-1].content[0].text
        else:
            text_content = ""
    except Exception as e:
        logger.warning(f"Interactions failed in evaluate_and_score_node, falling back to generate_content: {e}")
        response = await client.aio.models.generate_content(
            model=settings.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ScoreResult
            )
        )
        text_content = response.text
    
    if not text_content:
        # Fallback if the model refused to answer or returned an empty response
        result_data = ScoreResult(
            scores=PillarScores(performance=0, scalability=0, security=0, reliability=0, maintainability=0, cost_efficiency=0),
            evaluation_summary="Failed to generate evaluation due to model filter or error."
        )
    else:
        try:
            result_data = ScoreResult.model_validate_json(text_content)
        except Exception as e:
            print(f"Failed to parse ScoreResult JSON: {e}")
            result_data = ScoreResult(
                scores=PillarScores(performance=0, scalability=0, security=0, reliability=0, maintainability=0, cost_efficiency=0),
                evaluation_summary="Model returned invalid JSON format."
            )
            
    scores = result_data.scores
    
    project_id = ctx.state.get("project_id", "default_proj")
    current_round = ctx.state.get("current_round", 1)
    
    judge_directive = ctx.state.get("latest_judge_directive", None)
        
    new_round = DebateRound(
        round_number=current_round,
        proposal_draft=proposal,
        critique=combined_critiques,
        scores=scores,
        judge_directive=judge_directive
    )
    
    import json
    FilesystemJail.write_project_file(project_id, f"round_{current_round}.json", new_round.model_dump_json())
    
    consensus = scores.meets_threshold(settings.gate_threshold)
    ctx.state["consensus_achieved"] = consensus
    
    ctx.state["latest_judge_directive"] = None
    ctx.state["current_round"] = current_round + 1
    
    if consensus or current_round >= settings.max_rounds:
        ctx.state["consensus_achieved"] = True
        yield Event(output=ctx.state.to_dict(), route="synthesize", custom_metadata={"state": ctx.state.to_dict()})
        return
    
    # Save the proposal in state so the next iteration can read it if resumed
    ctx.state["latest_proposal"] = proposal
    
    message_text = (
        f"Round {current_round} complete. "
        f"Scores: P:{scores.performance:.2f} S:{scores.scalability:.2f} Sec:{scores.security:.2f} "
        f"R:{scores.reliability:.2f} M:{scores.maintainability:.2f} C:{scores.cost_efficiency:.2f}. "
        f"Reply 'SYNTHESIZE' to force finish, 'CONTINUE' to proceed, or provide a text directive."
    )
    # Rule 3 Fix: We didn't reach consensus, so we yield RequestInput to allow HITL intervention
    yield RequestInput(
        payload={"name": "judge_review"},
        message=message_text
    )
    
    yield Event(output="Waiting for judge review", route="review", custom_metadata={"state": ctx.state.to_dict()})
    return

@node
async def synthesis_node(ctx: Context, node_input: dict) -> Event:
    """Node 5: Compiles the final PRD.md and ARCHITECTURE.md and writes them safely."""
    client = get_genai_client()
    project_id = ctx.state.get("project_id", "default_proj")
    concept = ctx.state.get("concept", "")
    
    current_round = ctx.state.get("current_round", 1)
    rounds_count = current_round - 1
    history_text = ""
    
    import json
    for i in range(1, rounds_count + 1):
        try:
            round_data = FilesystemJail.read_project_file(project_id, f"round_{i}.json")
            r = json.loads(round_data)
            history_text += f"\n--- Round {r.get('round_number')} Scores: {r.get('scores')} ---\nPROPOSAL:\n{r.get('proposal_draft')}\n\nCRITIQUE:\n{r.get('critique')}\n"
        except Exception:
            pass

    prd_prompt = f"""
    You are the Principal Product Owner. 
    Synthesize the final, rigorous Product Requirements Document (PRD) for the concept: "{concept}"
    using the following architectural debate history and resolutions:
    {history_text}
    
    Include: 1. Goal Description, 2. Target Persona & Use Cases, 3. Complete functional requirements, 4. Non-Functional constraints, and 5. A numbered, horizontal implementation TASKLIST.
    """
    try:
        prd_response = await client.aio.interactions.create(model=settings.model_id, input=prd_prompt)
        prd_content = prd_response.steps[-1].content[0].text
    except Exception as e:
        logger.warning(f"Interactions failed for PRD synthesis, falling back: {e}")
        prd_response = await client.aio.models.generate_content(model=settings.model_id, contents=prd_prompt)
        prd_content = prd_response.text

    arch_prompt = f"""
    You are the Elite Software Architect.
    Synthesize the final, rigorous ARCHITECTURE.md design blueprint for the concept: "{concept}"
    incorporating all security, performance, scaling, and maintainability details agreed during this debate:
    {history_text}
    
    Format following strict Hexagonal Architecture / clean-code geometry guidelines.
    """
    
    try:
        arch_response = await client.aio.interactions.create(model=settings.model_id, input=arch_prompt)
        arch_content = arch_response.steps[-1].content[0].text
    except Exception as e:
        logger.warning(f"Interactions failed for ARCHITECTURE synthesis, falling back: {e}")
        arch_response = await client.aio.models.generate_content(model=settings.model_id, contents=arch_prompt)
        arch_content = arch_response.text

    FilesystemJail.write_project_file(project_id, "PRD.md", prd_content)
    FilesystemJail.write_project_file(project_id, "ARCHITECTURE.md", arch_content)

    ctx.state["final_prd"] = "[Saved to PRD.md]"
    ctx.state["final_architecture"] = "[Saved to ARCHITECTURE.md]"

    state_dump = ctx.state.to_dict()
    FilesystemJail.write_project_file(project_id, "state.json", json.dumps(state_dump, indent=2))

    return Event(output=ctx.state.to_dict(), custom_metadata={"state": ctx.state.to_dict()})

# Stitching the complete ADK 2.0 Workflow
root_agent = Workflow(
    name="architect_debate",
    edges=[
        ('START', initialize_debate),
        (initialize_debate, grill_node),
        (grill_node, {"ask_user": grill_node, "ready": performance_agent_node}),
        (performance_agent_node, (security_agent_node, sre_agent_node)),
        ((security_agent_node, sre_agent_node), join_critiques),
        (join_critiques, evaluate_and_score_node),
        (evaluate_and_score_node, {"continue": performance_agent_node, "synthesize": synthesis_node, "review": evaluate_and_score_node}),
    ],
    state_schema=DebateState,
)

# Wrapping into a Resumable App for human interrupts
app = App(
    name="debate_app",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True),
)
