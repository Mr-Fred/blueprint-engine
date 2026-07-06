import asyncio
import os
import logging
from pathlib import Path
from google import genai
from google.genai import types
from google.adk.workflow import node
from google.adk.agents.context import Context
from google.adk.events.event import Event

from app.config import settings
from app.shared_state import ACTIVE_DIRECTIVES
from app.utils import load_matching_skills
from app.agents.sre.prompt import get_sre_prompt

logger = logging.getLogger(__name__)

def get_genai_client() -> genai.Client:
    """Initializes and returns the Google Gen AI client based on configuration settings."""
    return settings.get_genai_client()

@node
async def sre_agent_node(ctx: Context, node_input: str) -> Event:
    """The Site Reliability Engineer critiques the proposal draft.
    
    Streams tokens in real time to the frontend SSE client, then yields the final complete audit critique
    to downstream join nodes in the graph.
    """
    client = get_genai_client()
    project_id = ctx.state.get("project_id", "default_proj")
    proposal = node_input
    
    # Extract any active judge feedback directive from shared registries or state
    judge_directive = ACTIVE_DIRECTIVES.get(project_id) or ctx.state.get("latest_judge_directive", None)

    # Dynamically load matching domain skills from local skills/ directory without crossing folder boundaries
    skills_dir = Path(__file__).parent / "skills"
    caveman_trigger = " caveman mode" if ctx.state.get("caveman_mode", True) else ""
    matched_skills = load_matching_skills(skills_dir, f"{proposal}{caveman_trigger}")

    prompt = get_sre_prompt(proposal, judge_directive=judge_directive, skills_context=matched_skills)

    previous_interaction_id = ctx.state.get("sre_interaction_id")
    critique_text = ""

    if settings.mock_mode:
        critique_text = "### [MOCK MODE] SRE & Scalability Audit\n\n- **Chaos Engineering**: Add automated chaos mesh testing for multi-region Spanner failovers.\n- **Observability**: Export distributed OpenTelemetry traces to Google Cloud Trace with 1% sampling.\n- **SLOs & Alerts**: Establish error budgets with paging rules triggered when P99 latency exceeds 250ms.\n"
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
                    ctx.state["sre_interaction_id"] = chunk.id
        except Exception as e:
            logger.warning(f"Interactions API failed for sre agent, falling back to generate_content_stream: {e}")
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

    yield Event(output=critique_text, custom_metadata={"state": ctx.state.to_dict()})

