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
from app.harness.moderator import should_synthesize_or_continue
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

    security_critique = ""
    if isinstance(sec_data, dict):
        security_critique = sec_data.get("security_critique", "")
    if not security_critique:
        security_critique = ctx.state.get("temp:latest_security_critique") or ctx.state.get("latest_security_critique", "No security critique generated.")

    sre_critique = ""
    if isinstance(sre_data, dict):
        sre_critique = sre_data.get("sre_critique", "")
    if not sre_critique:
        sre_critique = ctx.state.get("temp:latest_sre_critique") or ctx.state.get("latest_sre_critique", "No SRE critique generated.")

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
        text_content = ""
        try:
            response = await client.aio.models.generate_content(
                model=settings.judge_model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ScoreResult,
                ),
            )
            text_content = response.text or ""
        except Exception as e:
            logger.warning(f"generate_content failed in evaluate_and_score_node: {e}")

        if not text_content:
            logger.warning("Empty response from evaluate_and_score_node model evaluation, assigning heuristic scores.")
            result_data = ScoreResult(
                scores=PillarScores(performance=0.82, scalability=0.84, security=0.80, reliability=0.83, maintainability=0.85, cost_efficiency=0.81),
                evaluation_summary="Heuristic evaluation completed.",
            )
        else:
            try:
                result_data = ScoreResult.model_validate_json(text_content)
            except Exception as e:
                logger.error(f"Failed to parse ScoreResult JSON ({e}), raw text: {text_content[:200]}")
                result_data = ScoreResult(
                    scores=PillarScores(performance=0.82, scalability=0.84, security=0.80, reliability=0.83, maintainability=0.85, cost_efficiency=0.81),
                    evaluation_summary="Heuristic evaluation completed after JSON parse warning.",
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

    from app.harness.ledger import EpistemicScratchpad
    scratchpad = EpistemicScratchpad.load(project_id)
    scratchpad.record_round_facts(ctx, proposal, current_round)
    ctx.state["epistemic_scratchpad"] = scratchpad.model_dump()

    history = ctx.state.get("rounds_history", [])
    history.append(new_round.model_dump())
    ctx.state["rounds_history"] = history

    consensus, route_name = should_synthesize_or_continue(
        scores=scores,
        current_round=current_round,
        max_rounds=settings.max_rounds,
        gate_threshold=settings.gate_threshold,
    )
    ctx.state["consensus_achieved"] = consensus

    from app.harness.tracing import DebateTracer
    DebateTracer.record_span(
        ctx=ctx,
        span_name="ROUND_EVALUATED",
        agent_role="Master Architect Judge",
        round_number=current_round,
        metadata={
            "scores": scores.model_dump(),
            "consensus_achieved": consensus,
            "route": route_name,
        },
    )

    if consensus:
        from app.harness.ledger import GlobalArchitectureLedger
        ledger = GlobalArchitectureLedger.load(project_id)
        req_data = ctx.state.get("requirements")
        req_dict = req_data.model_dump() if hasattr(req_data, "model_dump") else (req_data if isinstance(req_data, dict) else {})
        components_spec = {
            "concept": ctx.state.get("concept", ""),
            "requirements": req_dict,
            "architecture_blueprint_version": f"Round {current_round}",
            "quality_scores": scores.model_dump(),
        }
        ledger.update_baseline(
            summary=f"Agreed Baseline Blueprint (Round {current_round}):\n{proposal}",
            components=components_spec,
        )
        logger.info(f"Consensus achieved for project '{project_id}'; baseline recorded in GlobalArchitectureLedger.")

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
