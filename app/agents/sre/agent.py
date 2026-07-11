import asyncio
import os
import logging
from pathlib import Path
from typing import Any
from google import genai
from google.genai import types
from google.adk.workflow import node
from google.adk.agents.context import Context
from google.adk.events.event import Event

from app.config import settings
from app.shared_state import ACTIVE_DIRECTIVES
from app.utils import load_matching_skills, parse_node_input, extract_stream_chunk_text, extract_interaction_id
from app.agents.sre.prompt import get_sre_prompt

logger = logging.getLogger(__name__)

def get_genai_client() -> genai.Client:
    """Initializes and returns the Google Gen AI client based on configuration settings."""
    return settings.get_genai_client()

from app.types import SRERubricEvaluation

@node
async def sre_agent_node(ctx: Context, node_input: Any) -> Event:
    """The Site Reliability Engineer critiques the proposal draft using structured ADK 2.0 evaluation rubrics."""
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

    prompt = get_sre_prompt(proposal, judge_directive=judge_directive, skills_context=matched_skills)

    prompt = (
        f"You MUST return a valid JSON payload matching the SRERubricEvaluation schema.\n"
        f"Evaluate high availability (0.0-1.0), fault tolerance (0.0-1.0), observability (0.0-1.0), "
        f"and estimated uptime tier (99.9%, 99.99%, or SUB_99%).\n\n"
        f"{prompt}"
    )

    critique_text = ""
    rubric: SRERubricEvaluation

    if settings.mock_mode:
        rubric = SRERubricEvaluation(
            high_availability_score=0.92,
            fault_tolerance_score=0.90,
            observability_score=0.95,
            estimated_uptime_tier="99.99%",
            detailed_critique="### [MOCK MODE] SRE & Scalability Audit\n\n- **Chaos Engineering**: Add automated chaos mesh testing for multi-region Spanner failovers.\n- **Observability**: Export distributed OpenTelemetry traces to Google Cloud Trace with 1% sampling.\n- **SLOs & Alerts**: Establish error budgets with paging rules triggered when P99 latency exceeds 250ms.\n"
        )
        critique_text = rubric.detailed_critique
        yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=critique_text)]))
    else:
        previous_interaction_id = ctx.state.get("sre_interaction_id")
        try:
            response_stream = await client.aio.interactions.create(
                model=settings.auditor_model_id,
                input=prompt,
                stream=True,
                store=True,
                previous_interaction_id=previous_interaction_id,
                response_format=SRERubricEvaluation,
            )
            async for chunk in response_stream:
                text = extract_stream_chunk_text(chunk)
                if text:
                    critique_text += text
                    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))
                chunk_id = extract_interaction_id(chunk)
                if chunk_id:
                    ctx.state["sre_interaction_id"] = chunk_id
            if not critique_text.strip():
                raise ValueError("Empty stream returned from interactions API")
        except Exception as e:
            logger.warning(f"Interactions API failed for sre agent ({e}), falling back to generate_content_stream.")
            try:
                response_stream = await client.aio.models.generate_content_stream(
                    model=settings.auditor_model_id,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=SRERubricEvaluation,
                    ),
                )
                async for chunk in response_stream:
                    text = extract_stream_chunk_text(chunk)
                    if text:
                        critique_text += text
                        yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))
            except Exception as stream_err:
                logger.warning(f"generate_content_stream failed ({stream_err}), falling back to non-streaming generate_content.")
                res = await client.aio.models.generate_content(
                    model=settings.auditor_model_id,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=SRERubricEvaluation,
                    ),
                )
                critique_text = res.text or ""
                yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=critique_text)]))

        try:
            cleaned = critique_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:].rstrip("`").strip()
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:].rstrip("`").strip()
            rubric = SRERubricEvaluation.model_validate_json(cleaned)
            critique_text = rubric.detailed_critique
        except Exception as parse_err:
            logger.warning(f"Failed to parse SRERubricEvaluation JSON ({parse_err}), using fallback structured rubric.")
            rubric = SRERubricEvaluation(
                high_availability_score=0.85,
                fault_tolerance_score=0.85,
                observability_score=0.85,
                estimated_uptime_tier="99.9%",
                detailed_critique=critique_text or "### SRE Review\n\nEnsure multi-region redundancy, defensive circuit breaking, and structured OpenTelemetry tracing across hot paths."
            )

    ctx.state["latest_sre_rubric"] = rubric.model_dump()
    ctx.state["temp:latest_sre_critique"] = critique_text
    if isinstance(node_input, dict):
        output_payload = dict(node_input)
        output_payload["sre_critique"] = critique_text
        output_payload["sre_rubric"] = rubric.model_dump()
    else:
        output_payload = critique_text

    from app.harness.tracing import DebateTracer
    DebateTracer.record_span(
        ctx=ctx,
        span_name="AGENT_CRITIQUE_GENERATED",
        agent_role="Site Reliability Engineer",
        round_number=ctx.state.get("current_round", 1),
        metadata={
            "critique_chars": len(critique_text),
            "ha_score": rubric.high_availability_score,
            "fault_tolerance_score": rubric.fault_tolerance_score,
            "observability_score": rubric.observability_score,
            "uptime_tier": rubric.estimated_uptime_tier,
        },
    )
    state_dump = ctx.state.to_dict() if hasattr(ctx.state, "to_dict") else dict(ctx.state)
    yield Event(output=output_payload, custom_metadata={"state": state_dump, "sre_rubric": rubric.model_dump()})
