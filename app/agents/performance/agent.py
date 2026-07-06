import asyncio
import logging
from pathlib import Path
from typing import Any

from google import genai
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.workflow import node
from google.genai import types

from app.agents.performance.prompt import get_performance_prompt
from app.config import settings
from app.shared_state import ACTIVE_DIRECTIVES
from app.utils import load_matching_skills, parse_node_input

logger = logging.getLogger(__name__)

def get_genai_client() -> genai.Client:
    """Initializes and returns the Google Gen AI client based on configuration settings."""
    return settings.get_genai_client()


@node
async def grill_node(ctx: Context, node_input: Any) -> Event:
    """
    Node 1: Interactive Grilling Phase.
    Repeatedly interviews the user to resolve design dependencies until ready.
    Uses RequestInput to pause execution and prompt for user clarification.
    """
    node_input = parse_node_input(node_input)
    client = get_genai_client()
    project_id = ctx.state.get("project_id", "default_proj")
    concept = ctx.state.get("concept", "A new software project")
    question_count = ctx.state.get("grill_question_count", 0)
    max_questions = ctx.state.get("max_grill_questions", 3)
    previous_interaction_id = ctx.state.get("grill_interaction_id")

    # Maintain a log for the UI to render the chat history
    grill_history = ctx.state.get("grill_history", [])

    if ctx.state.get("grill_completed", False) or ctx.state.get("current_round", 1) > 1 or any(
        "READY" in msg.get("content", "") or "skipped" in msg.get("content", "").lower() or "proceeding" in msg.get("content", "").lower()
        for msg in grill_history
    ):
        ctx.state["grill_completed"] = True
        yield Event(output=concept, route="ready", custom_metadata={"state": ctx.state.to_dict()})
        return

    # Handle user responses injected via resume
    user_answer = ""

    if isinstance(node_input, dict) and "grill_question" in node_input:
        user_answer = str(node_input["grill_question"])

        if user_answer.strip() == "SKIP_INTERVIEW":
            grill_history.append({"role": "assistant", "content": "Interview manually skipped. Proceeding to architectural debate."})
            ctx.state["grill_history"] = grill_history
            ctx.state["grill_completed"] = True
            yield Event(output=concept, route="ready", custom_metadata={"state": ctx.state.to_dict()})
            return

        question_count += 1
        ctx.state["grill_question_count"] = question_count
        grill_history.append({"role": "user", "content": user_answer})
        ctx.state["grill_history"] = grill_history

        if question_count >= max_questions:
            grill_history.append({"role": "assistant", "content": "I have all the context I need. Proceeding to architectural debate."})
            ctx.state["grill_history"] = grill_history
            ctx.state["grill_completed"] = True
            yield Event(output=concept, route="ready", custom_metadata={"state": ctx.state.to_dict()})
            return

    if not previous_interaction_id:
        prompt = f"""
        You are the Lead Performance Architect preparing to design: "{concept}".
        Your goal is to grill the user to resolve critical architectural design dependencies.
        Interview him relentlessly about every aspect of this project until you reach a shared understanding.
        Walk down each branch of the design tree, resolving dependencies between decisions one-by-one.
        For each question, provide your recommended answer. Ask the questions one at a time.
        """
    else:
        prompt = user_answer

    if question_count >= max_questions:
        prompt += "\nCRITICAL: You have reached the maximum number of questions. You MUST reply exactly with: READY"
    else:
        prompt += f"\nIf you fully understand the requirements and are ready to start proposing the architecture, reply exactly with: READY\nOtherwise, ask EXACTLY ONE focused, clarifying question. You have {max_questions - question_count} questions remaining."

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
                model=settings.model_id,
                input=prompt,
                previous_interaction_id=previous_interaction_id
            )

            if hasattr(response, "id") and response.id:
                ctx.state["grill_interaction_id"] = response.id

            text = response.steps[-1].content[0].text.strip()
        except Exception as e:
            logger.warning(f"Interactions failed in grill_node, falling back to generate_content: {e}")
            # Standard stateless fallback logic requires manual history injection
            fallback_prompt = f"""
            You are the Lead Performance Architect preparing to design: "{concept}".
            Your goal is to grill the user to resolve critical architectural design dependencies.
            Interview him relentlessly about every aspect of this project until you reach a shared understanding.
            Walk down each branch of the design tree, resolving dependencies between decisions one-by-one.
            For each question, provide your recommended answer. Ask the questions one at a time.
            """
            if grill_history:
                history_str = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in grill_history])
                fallback_prompt += f"\n\nConversation History:\n{history_str}\n"

            if question_count >= max_questions:
                fallback_prompt += "\nCRITICAL: You have reached the maximum number of questions. You MUST reply exactly with: READY"
            else:
                fallback_prompt += f"\nIf you fully understand the requirements and are ready to start proposing the architecture, reply exactly with: READY\nOtherwise, ask EXACTLY ONE focused, clarifying question. You have {max_questions - question_count} questions remaining."

            fallback_res = await client.aio.models.generate_content(
                model=settings.model_id,
                contents=fallback_prompt
            )
            text = fallback_res.text.strip()

    # Append model's output to UI log
    grill_history.append({"role": "assistant", "content": text})
    ctx.state["grill_history"] = grill_history

    if text == "READY":
        ctx.state["grill_completed"] = True
        yield Event(output=concept, route="ready", custom_metadata={"state": ctx.state.to_dict()})
        return

    yield Event(
        content=types.Content(role="model", parts=[types.Part.from_text(text=text)]),
        custom_metadata={"state": ctx.state.to_dict()}
    )

    # Pause the graph and ask the user
    yield RequestInput(
        payload={"name": "grill_question"},
        message=text
    )

    # Route back to itself so the resumed graph executes this node again with the user's answer
    yield Event(output="Waiting for user", route="ask_user", custom_metadata={"state": ctx.state.to_dict()})
    return

@node
async def performance_agent_node(ctx: Context, node_input: str) -> Event:
    """
    Node 2: Performance Lead Architect.
    Uses stateful Interactions API with a defensive fallback to standard generate_content_stream
    to ensure reliability and prevent blocking on unsupported backends/models.
    """
    client = get_genai_client()
    project_id = ctx.state.get("project_id", "default_proj")
    concept = ctx.state.get("concept", "")
    current_round = ctx.state.get("current_round", 1)
    history = ctx.state.get("rounds_history", [])

    # Extract any active judge feedback directive from shared registries or state
    judge_directive = ACTIVE_DIRECTIVES.get(project_id) or ctx.state.get("latest_judge_directive", None)

    # Dynamically load matching architectural and schema skills based on concept, past critiques, and judge directives
    last_critique = history[-1].get("critique", "") if history else ""
    caveman_trigger = " caveman mode" if ctx.state.get("caveman_mode", True) else ""
    match_text = f"{concept} {last_critique} {judge_directive or ''}{caveman_trigger}"
    skills_dir = Path(__file__).parent / "skills"
    matched_skills = load_matching_skills(skills_dir, match_text)

    prompt = get_performance_prompt(
        concept=concept,
        current_round=current_round,
        history=history,
        judge_directive=judge_directive,
        skills_context=matched_skills
    )

    previous_interaction_id = ctx.state.get("performance_interaction_id")
    proposal_text = ""

    if settings.mock_mode:
        proposal_text = f"### [MOCK MODE] Architectural Blueprint: {concept} (Round {current_round})\n\n**1. High-Level Architecture**: Multi-region Kubernetes cluster running on Google Cloud with Global Load Balancing.\n**2. Database & Caching**: Cloud Spanner for global linearizability paired with Redis Cluster for sub-millisecond caching.\n**3. Performance Optimization**: Asynchronous task workers with Pub/Sub and CDN edge caching enabled.\n"
        for line in proposal_text.splitlines(keepends=True):
            yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=line)]))
            await asyncio.sleep(0.05)
    else:
        try:
            # Try stateful interactions API first
            response_stream = await client.aio.interactions.create(
                model=settings.model_id,
                input=prompt,
                stream=True,
                store=True,
                previous_interaction_id=previous_interaction_id
            )
            async for chunk in response_stream:
                if getattr(chunk, "steps", None):
                    step = chunk.steps[-1]
                    if step.content and step.content[0].text:
                        text = step.content[0].text
                        proposal_text += text
                        yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))

                # Save the server-side stateful interaction ID
                if hasattr(chunk, "id") and chunk.id:
                    ctx.state["performance_interaction_id"] = chunk.id
        except Exception as e:
            logger.warning(f"Interactions API failed for performance agent, falling back to generate_content_stream: {e}")
            # Bounded fallback to standard generation stream
            response_stream = await client.aio.models.generate_content_stream(
                model=settings.model_id,
                contents=prompt
            )
            async for chunk in response_stream:
                text = chunk.text or ""
                if text:
                    proposal_text += text
                    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))

    ctx.state["latest_proposal"] = proposal_text
    yield Event(output=proposal_text, custom_metadata={"state": ctx.state.to_dict()})
