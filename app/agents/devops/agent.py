import os
import logging
from google import genai
from google.genai import types
from google.adk.workflow import node
from google.adk.agents.context import Context
from google.adk.events.event import Event

from app.config import settings
from app.shared_state import ACTIVE_DIRECTIVES
from app.agents.devops.prompt import get_devops_prompt

logger = logging.getLogger(__name__)

def get_genai_client() -> genai.Client:
    """Initializes and returns the Google Gen AI client based on configuration settings."""
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() in ["true", "1"]
    return genai.Client(vertexai=use_vertex, location="global")

@node
async def devops_agent_node(ctx: Context, node_input: str):
    """The DevOps & Maintainability Lead critiques the proposal draft.
    
    Streams tokens in real time to the frontend SSE client, then yields the final complete audit critique
    to downstream join nodes in the graph.
    """
    client = get_genai_client()
    project_id = ctx.state.get("project_id", "default_proj")
    proposal = node_input
    
    # Extract any active judge feedback directive from shared registries or state
    judge_directive = ACTIVE_DIRECTIVES.get(project_id) or ctx.state.get("latest_judge_directive", None)

    prompt = get_devops_prompt(proposal, judge_directive=judge_directive)

    previous_interaction_id = ctx.state.get("devops_interaction_id")
    critique_text = ""

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
                    critique_text += text
                    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))
            
            # Save the server-side stateful interaction ID
            if hasattr(chunk, "id") and chunk.id:
                ctx.state["devops_interaction_id"] = chunk.id
    except Exception as e:
        logger.warning(f"Interactions API failed for devops agent, falling back to generate_content_stream: {e}")
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

    yield Event(output=critique_text, state=ctx.state.to_dict())
