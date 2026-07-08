import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from google import genai
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.workflow import node
from google.genai import types
from pydantic import BaseModel, Field

from app.agents.judge.prompt import get_judge_evaluation_prompt
from app.config import settings
from app.shared_state import ACTIVE_DIRECTIVES
from app.types import DebateRound, PillarScores
from app.utils import FilesystemJail, load_matching_skills, parse_node_input

logger = logging.getLogger(__name__)


def get_genai_client() -> genai.Client:
    """Initializes and returns the Google Gen AI client based on configuration settings."""
    return settings.get_genai_client()


class ScoreResult(BaseModel):
    """Structured evaluation schema for the 6 quality pillars."""
    scores: PillarScores = Field(..., description="Scores for the 6 pillars")
    evaluation_summary: str = Field(..., description="Detailed summary explaining the scores")


def should_synthesize_or_continue(
    scores: Optional[PillarScores] = None,
    current_round: int = 1,
    max_rounds: int = 3,
    gate_threshold: float = 0.85,
    user_choice: str = "",
) -> Tuple[bool, str]:
    """Deterministic routing decision for evaluate_and_score_node.

    Returns:
        Tuple[bool, str]: (consensus_achieved: bool, route_name: str)
            route_name is one of 'synthesize', 'continue', or 'review'.
    """
    clean_choice = user_choice.strip().upper()
    if clean_choice == "SYNTHESIZE":
        return True, "synthesize"
    if clean_choice == "CONTINUE" or (clean_choice and clean_choice != "SYNTHESIZE"):
        return False, "continue"

    if scores is not None:
        consensus = scores.meets_threshold(gate_threshold)
        if consensus or current_round >= max_rounds:
            return True, "synthesize"

    return False, "review"


@node
async def evaluate_and_score_node(ctx: Context, node_input: Any) -> Event:
    """Node 4: Evaluates proposal and critiques, scores them on the 6 pillars, and routes to next step."""
    node_input = parse_node_input(node_input)

    # 1. Handle Human-In-The-Loop Resumption Seam
    if isinstance(node_input, dict) and "judge_review" in node_input:
        user_choice = str(node_input["judge_review"]).strip()
        consensus, route_name = should_synthesize_or_continue(user_choice=user_choice)
        if route_name == "synthesize":
            ctx.state["consensus_achieved"] = True
            yield Event(output=ctx.state.to_dict(), route="synthesize", custom_metadata={"state": ctx.state.to_dict()})
            return
        elif user_choice.upper() not in {"CONTINUE", ""}:
            ctx.state["latest_judge_directive"] = user_choice

        proposal = ctx.state.get("latest_proposal", "")
        ctx.state["temp:latest_proposal"] = proposal
        yield Event(output=proposal, route="continue", custom_metadata={"state": ctx.state.to_dict()})
        return


    client = get_genai_client()

    # 2. Extract parallel node outputs merged by JoinNode
    sec_data = node_input.get("security_agent_node", {}) if isinstance(node_input, dict) else {}
    sre_data = node_input.get("sre_agent_node", {}) if isinstance(node_input, dict) else {}

    security_critique = sec_data.get("security_critique", str(sec_data)) if isinstance(sec_data, dict) else str(sec_data)
    sre_critique = sre_data.get("sre_critique", str(sre_data)) if isinstance(sre_data, dict) else str(sre_data)

    proposal = ""
    if isinstance(sec_data, dict):
        proposal = sec_data.get("proposal", "")
    if not proposal and isinstance(sre_data, dict):
        proposal = sre_data.get("proposal", "")
    if not proposal:
        proposal = ctx.state.get("latest_proposal", "N/A")

    combined_critiques = f"--- SECURITY AUDIT ---\n{security_critique}\n\n--- SRE CRITIQUE ---\n{sre_critique}"

    # Dynamically load domain skills from local judge skills/ directory
    skills_dir = Path(__file__).parent / "skills"
    matched_skills = load_matching_skills(skills_dir, f"{proposal} {combined_critiques}")

    prompt = get_judge_evaluation_prompt(
        proposal=proposal,
        combined_critiques=combined_critiques,
        skills_context=matched_skills,
    )

    current_round = ctx.state.get("current_round", 1)

    if settings.mock_mode:
        sec_score = 0.80 if current_round == 1 else 0.89
        result_data = ScoreResult(
            scores=PillarScores(
                performance=0.88,
                scalability=0.90,
                security=sec_score,
                reliability=0.89,
                maintainability=0.91,
                cost_efficiency=0.86,
            ),
            evaluation_summary=f"[MOCK MODE] Round {current_round} evaluation completed locally.",
        )
        scores = result_data.scores
    else:
        try:
            response = await client.aio.interactions.create(
                model=settings.judge_model_id,
                input=prompt,
                response_format=ScoreResult.model_json_schema(),
            )
            if response.steps and response.steps[-1].content:
                text_content = response.steps[-1].content[0].text
            else:
                text_content = ""
        except Exception as e:
            logger.warning(f"Interactions failed in evaluate_and_score_node, falling back to generate_content: {e}")
            response = await client.aio.models.generate_content(
                model=settings.judge_model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ScoreResult,
                ),
            )
            text_content = response.text

        if not text_content:
            result_data = ScoreResult(
                scores=PillarScores(performance=0, scalability=0, security=0, reliability=0, maintainability=0, cost_efficiency=0),
                evaluation_summary="Failed to generate evaluation due to model filter or error.",
            )
        else:
            try:
                result_data = ScoreResult.model_validate_json(text_content)
            except Exception as e:
                logger.error(f"Failed to parse ScoreResult JSON: {e}")
                result_data = ScoreResult(
                    scores=PillarScores(performance=0, scalability=0, security=0, reliability=0, maintainability=0, cost_efficiency=0),
                    evaluation_summary="Model returned invalid JSON format.",
                )

        scores = result_data.scores

    project_id = ctx.state.get("project_id", "default_proj")
    judge_directive = ctx.state.get("latest_judge_directive", None)

    new_round = DebateRound(
        round_number=current_round,
        proposal_draft=proposal,
        critique=combined_critiques,
        scores=scores,
        judge_directive=judge_directive,
    )

    FilesystemJail.write_project_file(project_id, f"round_{current_round}.json", new_round.model_dump_json())

    history = ctx.state.get("rounds_history", [])
    history.append(new_round.model_dump())
    ctx.state["rounds_history"] = history

    consensus, route_name = should_synthesize_or_continue(
        scores=scores,
        current_round=current_round,
        max_rounds=settings.max_rounds,
        gate_threshold=settings.gate_threshold,
    )
    ctx.state["consensus_achieved"] = False

    ctx.state["latest_judge_directive"] = None
    ctx.state["current_round"] = current_round + 1

    if route_name == "synthesize":
        yield Event(output=ctx.state.to_dict(), route="synthesize", custom_metadata={"state": ctx.state.to_dict()})
        return

    ctx.state["latest_proposal"] = proposal

    message_text = (
        f"Round {current_round} complete. "
        f"Scores: P:{scores.performance:.2f} S:{scores.scalability:.2f} Sec:{scores.security:.2f} "
        f"R:{scores.reliability:.2f} M:{scores.maintainability:.2f} C:{scores.cost_efficiency:.2f}. "
        f"Reply 'SYNTHESIZE' to force finish, 'CONTINUE' to proceed, or provide a text directive."
    )
    yield Event(
        content=types.Content(role="model", parts=[types.Part.from_text(text="Round complete, awaiting judge review")]),
        custom_metadata={"state": ctx.state.to_dict()},
    )
    yield RequestInput(
        payload={"name": "judge_review"},
        message=message_text,
    )

    yield Event(output="Waiting for judge review", route="review", custom_metadata={"state": ctx.state.to_dict()})
    return
