import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

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
from app.agents.devops.agent import devops_agent_node

# Initialize Google Gen AI Client
def get_genai_client() -> genai.Client:
    # ADK uses Vertex AI by default, falling back to Gemini API
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() in ["true", "1"]
    return genai.Client(vertexai=use_vertex, location="global")

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
    
    # Store initial concept and project_id in the workflow state
    ctx.state["project_id"] = project_id
    ctx.state["concept"] = concept
    ctx.state["current_round"] = 1
    ctx.state["rounds_history"] = []
    ctx.state["consensus_achieved"] = False
    
    return Event(output=concept, state=ctx.state.to_dict())

# Join Node to combine Security and DevOps critiques
join_critiques = JoinNode(name="merge_critiques")

# Helper schema for structured score evaluation
class ScoreResult(BaseModel):
    scores: PillarScores = Field(..., description="Scores for the 6 pillars")
    evaluation_summary: str = Field(..., description="Detailed summary explaining the scores")

@node
def evaluate_and_score_node(ctx: Context, node_input: dict) -> Event:
    """Node 4: Evaluates proposal and critiques, scores them on the 6 pillars, and routes."""
    client = get_genai_client()
    
    # Extract parallel node outputs merged by JoinNode
    # security_agent_node output is keyed as 'security_agent_node'
    # devops_agent_node output is keyed as 'devops_agent_node'
    security_critique = node_input.get("security_agent_node", "")
    devops_critique = node_input.get("devops_agent_node", "")
    
    proposal = ctx.state.get("latest_proposal", "")
    if not proposal:
        # Fallback to last round's draft
        proposal = "N/A"
        
    combined_critiques = f"--- SECURITY AUDIT ---\n{security_critique}\n\n--- DEVOPS CRITIQUE ---\n{devops_critique}"

    prompt = f"""
    You are the Independent Master Architect Judge.
    Evaluate the following proposed design against its security and DevOps critiques.
    
    Proposed Design:
    {proposal}
    
    Critiques & Audits:
    {combined_critiques}
    
    Assign a score between 0.0 (failing/flawed) and 1.0 (perfectly ready) for the 6 software quality pillars.
    """

    response = client.models.generate_content(
        model=settings.model_id,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ScoreResult
        )
    )
    
    # Parse structured JSON response
    result_data = ScoreResult.model_validate_json(response.text)
    scores = result_data.scores
    
    project_id = ctx.state.get("project_id", "default_proj")
    current_round = ctx.state.get("current_round", 1)
    
    # Read active directive (and pop it from the shared register so it's not reused next round)
    judge_directive = ACTIVE_DIRECTIVES.get(project_id) or ctx.state.get("latest_judge_directive", None)
    if project_id in ACTIVE_DIRECTIVES:
        del ACTIVE_DIRECTIVES[project_id]
        
    # Record this round in history
    new_round = DebateRound(
        round_number=current_round,
        proposal_draft=proposal,
        critique=combined_critiques,
        scores=scores,
        judge_directive=judge_directive
    )
    
    # Update local state list
    history = ctx.state.get("rounds_history", [])
    history.append(new_round.model_dump())
    ctx.state["rounds_history"] = history
    
    # Check if consensus achieved
    consensus = scores.meets_threshold(settings.gate_threshold)
    ctx.state["consensus_achieved"] = consensus
    
    # Synchronize with global DEBATE_SESSIONS registry (lazy import prevents circular issues)
    try:
        from app.main import DEBATE_SESSIONS
        if project_id in DEBATE_SESSIONS:
            DEBATE_SESSIONS[project_id].current_round = current_round
            DEBATE_SESSIONS[project_id].rounds_history = [
                DebateRound.model_validate(r) for r in ctx.state["rounds_history"]
            ]
            DEBATE_SESSIONS[project_id].consensus_achieved = consensus
    except Exception as e:
        # Graceful fallback if not running from main FastAPI context (e.g. tests)
        pass
    
    # Reset latest judge directive now that it has been addressed in this round
    ctx.state["latest_judge_directive"] = None
    
    # Increment round counter
    ctx.state["current_round"] = current_round + 1
    
    # Check for force synthesis override or round limits
    force_synthesis = ctx.state.get("force_synthesis_flag", False) or FORCE_SYNTHESIS_FLAGS.get(project_id, False)
    if project_id in FORCE_SYNTHESIS_FLAGS:
        del FORCE_SYNTHESIS_FLAGS[project_id]
        
    if consensus or force_synthesis or current_round >= settings.max_rounds:
        ctx.state["consensus_achieved"] = True
        return Event(output=ctx.state.to_dict(), route="synthesize", state=ctx.state.to_dict())
    
    # Otherwise, loop back. We also save the proposal in state so the next iteration can read it.
    ctx.state["latest_proposal"] = proposal
    return Event(output=proposal, route="continue", state=ctx.state.to_dict())

@node
def synthesis_node(ctx: Context, node_input: dict) -> Event:
    """Node 5: Compiles the final PRD.md and ARCHITECTURE.md and writes them safely."""
    client = get_genai_client()
    project_id = ctx.state.get("project_id", "default_proj")
    concept = ctx.state.get("concept", "")
    history = ctx.state.get("rounds_history", [])

    # Format the entire debate ledger
    history_text = ""
    for r in history:
        history_text += f"\n--- Round {r.get('round_number')} Scores: {r.get('scores')} ---\nPROPOSAL:\n{r.get('proposal_draft')}\n\nCRITIQUE:\n{r.get('critique')}\n"

    # 1. Synthesize PRD.md
    prd_prompt = f"""
    You are the Principal Product Owner. 
    Synthesize the final, rigorous Product Requirements Document (PRD) for the concept: "{concept}"
    using the following architectural debate history and resolutions:
    {history_text}
    
    Include: 1. Goal Description, 2. Target Persona & Use Cases, 3. Complete functional requirements, 4. Non-Functional constraints, and 5. A numbered, horizontal implementation TASKLIST.
    """
    prd_response = client.models.generate_content(model=settings.model_id, contents=prd_prompt)
    prd_content = prd_response.text

    # 2. Synthesize ARCHITECTURE.md
    arch_prompt = f"""
    You are the Elite Software Architect.
    Synthesize the final, rigorous ARCHITECTURE.md design blueprint for the concept: "{concept}"
    incorporating all security, performance, scaling, and maintainability details agreed during this debate:
    {history_text}
    
    Format following strict Hexagonal Architecture / clean-code geometry guidelines.
    """
    arch_response = client.models.generate_content(model=settings.model_id, contents=arch_prompt)
    arch_content = arch_response.text

    # Write files securely using our FilesystemJail utility
    FilesystemJail.write_project_file(project_id, "PRD.md", prd_content)
    FilesystemJail.write_project_file(project_id, "ARCHITECTURE.md", arch_content)

    ctx.state["final_prd"] = prd_content
    ctx.state["final_architecture"] = arch_content

    # Save full state to disk for future restoration
    import json
    state_dump = ctx.state.to_dict()
    FilesystemJail.write_project_file(project_id, "state.json", json.dumps(state_dump, indent=2))

    # Synchronize synthesized artifacts with global DEBATE_SESSIONS registry
    try:
        from app.main import DEBATE_SESSIONS
        if project_id in DEBATE_SESSIONS:
            DEBATE_SESSIONS[project_id].consensus_achieved = True
            DEBATE_SESSIONS[project_id].final_prd = prd_content
            DEBATE_SESSIONS[project_id].final_architecture = arch_content
    except Exception as e:
        pass

    return Event(output=ctx.state.to_dict(), state=ctx.state.to_dict())

# Stitching the complete ADK 2.0 Workflow
root_agent = Workflow(
    name="architect_debate",
    edges=[
        ('START', initialize_debate),
        (initialize_debate, performance_agent_node),
        (performance_agent_node, (security_agent_node, devops_agent_node)),
        ((security_agent_node, devops_agent_node), join_critiques),
        (join_critiques, evaluate_and_score_node),
        (evaluate_and_score_node, {"continue": performance_agent_node, "synthesize": synthesis_node}),
    ],
    state_schema=DebateState,
)

# Wrapping into a Resumable App for human interrupts
app = App(
    name="debate_app",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True),
)
