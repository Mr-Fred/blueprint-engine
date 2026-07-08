import asyncio
import logging
from pathlib import Path
from typing import Any

from google import genai
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.workflow import node
from google.genai import types

from app.agents.security.prompt import get_security_prompt
from app.config import settings
from app.shared_state import ACTIVE_DIRECTIVES
from app.utils import load_matching_skills, parse_node_input

logger = logging.getLogger(__name__)

def get_genai_client() -> genai.Client:
    """Initializes and returns the Google Gen AI client based on configuration settings."""
    return settings.get_genai_client()

@node
async def security_agent_node(ctx: Context, node_input: Any) -> Event:
    """The Security & Resilience Auditor critiques the proposal draft.

    Streams tokens in real time to the frontend SSE client, then yields the final complete audit critique
    to downstream join nodes in the graph.
    """
    node_input = parse_node_input(node_input)
    client = get_genai_client()
    project_id = ctx.state.get("project_id", "default_proj")
    proposal = node_input.get("proposal", str(node_input)) if isinstance(node_input, dict) else str(node_input)

    # Extract any active judge feedback directive from shared registries or state
    judge_directive = ACTIVE_DIRECTIVES.get(project_id) or ctx.state.get("latest_judge_directive", None)

    # Dynamically load matching domain skills from local skills/ directory without crossing folder boundaries
    skills_dir = Path(__file__).parent / "skills"
    caveman_trigger = " caveman mode" if ctx.state.get("caveman_mode", True) else ""
    matched_skills = load_matching_skills(skills_dir, f"{proposal}{caveman_trigger}")

    prompt = get_security_prompt(proposal, judge_directive=judge_directive, skills_context=matched_skills)

    previous_interaction_id = ctx.state.get("security_interaction_id")
    critique_text = ""

    if settings.mock_mode:
        critique_text = "### [MOCK MODE] Security Critique & Hardening\n\n- **Zero-Trust Auth**: Require Workload Identity Federation instead of static service account keys.\n- **Data Encryption**: Enforce Customer-Managed Encryption Keys (CMEK) on Spanner and Redis buckets.\n- **Rate Limiting**: Add Cloud Armor edge security policies to mitigate DDoS and brute-force attacks.\n"
        for line in critique_text.splitlines(keepends=True):
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
                        critique_text += text
                        yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))

                # Save the server-side stateful interaction ID
                if hasattr(chunk, "id") and chunk.id:
                    ctx.state["security_interaction_id"] = chunk.id
        except Exception as e:
            logger.warning(f"Interactions API failed for security agent, falling back to generate_content_stream: {e}")
            # Bounded fallback to standard generation stream
            response_stream = await client.aio.models.generate_content_stream(
                model=settings.model_id,
                contents=prompt
            )
            async for chunk in response_stream:
                text = chunk.text or ""
                if text:
                    critique_text += text
                    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))

    if isinstance(node_input, dict):
        output_payload = dict(node_input)
        output_payload["security_critique"] = critique_text
    else:
        output_payload = critique_text

    yield Event(output=output_payload, custom_metadata={"state": ctx.state.to_dict()})

