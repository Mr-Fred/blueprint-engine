import logging
from typing import Any

from google import genai
from google.adk.agents.context import Context
from google.adk.apps import App, ResumabilityConfig
from google.adk.events.event import Event
from google.adk.workflow import JoinNode, Workflow, node

# Import modular agent nodes across all 5 specialized roles
from app.agents.judge.agent import evaluate_and_score_node
from app.agents.performance.agent import grill_node, performance_agent_node
from app.agents.security.agent import security_agent_node
from app.agents.sre.agent import sre_agent_node
from app.agents.synthesizer.agent import synthesis_node
from app.config import settings
from app.types import DebateState
from app.utils import parse_node_input

logger = logging.getLogger(__name__)


def get_genai_client() -> genai.Client:
    """Creates a Google GenAI Client configured for either Vertex AI or standard Gemini API."""
    return settings.get_genai_client()


@node
def initialize_debate(ctx: Context, node_input: Any) -> Event:
    """Node 1: Receives the user's software concept and boots up the baseline state."""
    node_input = parse_node_input(node_input)

    if isinstance(node_input, dict):
        project_id = node_input.get("project_id", "default_proj")
        concept = node_input.get("concept", "")
        caveman_mode = node_input.get("caveman_mode", True)
    else:
        project_id = "default_proj"
        concept = str(node_input)
        caveman_mode = True

    if project_id and project_id != "default_proj":
        ctx.state["project_id"] = project_id
    elif "project_id" not in ctx.state:
        ctx.state["project_id"] = project_id

    # Check explicit resume inputs first
    if isinstance(node_input, dict) and "judge_review" in node_input:
        return Event(output=node_input, route="review", custom_metadata={"state": ctx.state.to_dict()})
    elif isinstance(node_input, dict) and "grill_question" in node_input:
        return Event(output=node_input, route="grill", custom_metadata={"state": ctx.state.to_dict()})

    # If grilling has completed or debate rounds already exist, route to 'ready'
    if ctx.state.get("grill_completed", False) or len(ctx.state.get("rounds_history", [])) > 0:
        return Event(output=ctx.state.get("concept", concept), route="ready", custom_metadata={"state": ctx.state.to_dict()})

    # Store initial concept and project_id in the workflow state for fresh sessions
    ctx.state["project_id"] = project_id
    ctx.state["concept"] = concept
    ctx.state["caveman_mode"] = caveman_mode
    ctx.state["current_round"] = 1
    ctx.state["rounds_history"] = []
    ctx.state["consensus_achieved"] = False

    return Event(output=concept, route="grill", custom_metadata={"state": ctx.state.to_dict()})


# Join Node to combine Security and DevOps critiques
join_critiques = JoinNode(name="merge_critiques")

# Stitching the complete ADK 2.0 Workflow across modular agent boundaries
root_agent = Workflow(
    name="architect_debate",
    edges=[
        ("START", initialize_debate),
        (initialize_debate, {"grill": grill_node, "review": evaluate_and_score_node, "ready": performance_agent_node}),
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
