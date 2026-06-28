import os
import logging
from google import genai
from google.genai import types
from google.adk.workflow import node
from google.adk.agents.context import Context
from google.adk.events.event import Event

from app.config import settings
from app.shared_state import ACTIVE_DIRECTIVES
from app.agents.performance.prompt import get_performance_prompt

logger = logging.getLogger(__name__)

def get_genai_client() -> genai.Client:
    """Initializes and returns the Google Gen AI client based on configuration settings."""
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() in ["true", "1"]
    return genai.Client(vertexai=use_vertex, location="global")

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

    prompt = get_performance_prompt(
        concept=concept,
        current_round=current_round,
        history=history,
        judge_directive=judge_directive
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
            if chunk.steps:
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
    yield Event(output=proposal_text, state=ctx.state.to_dict())
