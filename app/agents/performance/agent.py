import logging
import os
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
from app.utils import load_matching_skills

logger = logging.getLogger(__name__)

def get_genai_client() -> genai.Client:
    """Initializes and returns the Google Gen AI client based on configuration settings."""
    return settings.get_genai_client()


@node
async def grill_node(ctx: Context, node_input: Any):
    """Node that grills the user at the start of the debate to gather deep context via RequestInput."""
    client = get_genai_client()
    concept = ctx.state.get("concept", "")

    previous_interaction_id = ctx.state.get("grill_interaction_id")

    question_count = ctx.state.get("grill_question_count", 0)
    max_questions = 5

    # Maintain a log for the UI to render the chat history
    grill_history = ctx.state.get("grill_history", [])

    # Handle user responses injected via resume
    user_answer = ""

    # Securely extract the resume payload from ctx.user_content
    if ctx.user_content and ctx.user_content.role == "user" and ctx.user_content.parts:
        try:
            import json
            payload = json.loads(ctx.user_content.parts[0].text)
            if isinstance(payload, dict):
                node_input = payload
        except Exception:
            pass

    if isinstance(node_input, dict) and "grill_question" in node_input:
        user_answer = str(node_input["grill_question"])

        if user_answer.strip() == "SKIP_INTERVIEW":
            grill_history.append({"role": "assistant", "content": "Interview manually skipped. Proceeding to architectural debate."})
            ctx.state["grill_history"] = grill_history
            yield Event(output=concept, route="ready", custom_metadata={"state": ctx.state.to_dict()})
            return

        question_count += 1
        ctx.state["grill_question_count"] = question_count
        grill_history.append({"role": "user", "content": user_answer})
        ctx.state["grill_history"] = grill_history

        if question_count >= max_questions:
            grill_history.append({"role": "assistant", "content": "I have all the context I need. Proceeding to architectural debate."})
            ctx.state["grill_history"] = grill_history
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
async def performance_agent_node(ctx: Context, node_input: str):
    """The Performance & Scaling Architect proposes or refines the design blueprint.

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
