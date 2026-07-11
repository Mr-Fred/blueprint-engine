import logging

from google.adk.apps import App, ResumabilityConfig
from google.adk.workflow import JoinNode, Workflow

# Import Harness deterministic entry routing nodes
from app.harness.moderator import grill_node, initialize_debate

# Import modular agent nodes across all 5 specialized roles
from app.agents.judge.agent import evaluate_and_score_node
from app.agents.performance.agent import performance_agent_node
from app.agents.security.agent import security_agent_node
from app.agents.sre.agent import sre_agent_node
from app.agents.synthesizer.agent import synthesis_node
from app.types import DebateState

logger = logging.getLogger(__name__)

# Join Node to combine Security and DevOps critiques
join_critiques = JoinNode(name="merge_critiques")

# Declarative ADK 2.0 Workflow assembly across Harness routing and Agent modules
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
