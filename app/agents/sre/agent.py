import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from google import genai
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.workflow import node
from google.genai import types

from app.agents.sre.prompt import get_sre_prompt
from app.config import settings
from app.types import SRERubricEvaluation
from app.utils import (
    extract_interaction_id,
    extract_stream_chunk_text,
    load_matching_skills,
    parse_node_input,
)

logger = logging.getLogger(__name__)

def get_genai_client() -> genai.Client:
    """Initializes and returns the Google Gen AI client based on configuration settings."""
    return settings.get_genai_client()

@node
async def sre_agent_node(ctx: Context, node_input: Any) -> Event:
    """The Site Reliability Engineer critiques the proposal draft using structured ADK 2.0 evaluation rubrics."""
    node_input = parse_node_input(node_input)
    client = get_genai_client()
    project_id = ctx.state.get("project_id", "default_proj")
    proposal = node_input.get("proposal", str(node_input)) if isinstance(node_input, dict) else str(node_input)
    
    # Extract any active judge feedback directive from state
    judge_directive = ctx.state.get("latest_judge_directive", None)

    # Dynamically load matching domain skills from local skills/ directory without crossing folder boundaries
    skills_dir = Path(__file__).parent / "skills"
    caveman_trigger = " caveman mode" if ctx.state.get("caveman_mode", True) else ""
    matched_skills = load_matching_skills(skills_dir, f"{proposal}{caveman_trigger}")

    prompt = get_sre_prompt(proposal, judge_directive=judge_directive, skills_context=matched_skills, project_id=project_id)

    prompt = (
        f"You MUST return a valid JSON payload matching the SRERubricEvaluation schema.\n"
        f"Evaluate high availability (0.0-1.0), fault tolerance (0.0-1.0), observability (0.0-1.0), "
        f"and estimated uptime tier (99.9%, 99.99%, or SUB_99%).\n\n"
        f"{prompt}"
    )

    critique_text = ""
    res: Any = None
    rubric: SRERubricEvaluation

    from app.harness.tools import format_tools_for_interactions, get_harness_tools
    harness_tools = get_harness_tools()

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
                tools=format_tools_for_interactions(harness_tools),
                stream=True,
                store=True,
                previous_interaction_id=previous_interaction_id,
                response_format=SRERubricEvaluation.model_json_schema(),
            )
            from app.utils import log_gemini_inspection
            async for chunk in response_stream:
                log_gemini_inspection("interactions.create_chunk", settings.auditor_model_id, chunk, {"role": "sre"})
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
            logger.warning(f"Interactions API failed for sre agent ({e}), falling back to stream_agent_with_tools.")
            try:
                from app.harness.tools import stream_agent_with_tools
                async for text in stream_agent_with_tools(
                    client=client,
                    model_id=settings.auditor_model_id,
                    prompt=prompt,
                    tools=harness_tools,
                    response_schema=SRERubricEvaluation,
                ):
                    critique_text += text
                    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))
            except Exception as stream_err:
                logger.warning(f"stream_agent_with_tools failed ({stream_err}).")

            if not critique_text.strip():
                logger.warning("Empty stream text for sre agent, running non-streaming text fallback with retry.")
                from app.utils import call_with_retry_on_429, log_gemini_inspection
                res = await call_with_retry_on_429(
                    lambda: client.aio.models.generate_content(
                        model=settings.auditor_model_id,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=SRERubricEvaluation,
                        ),
                    ),
                    max_retries=3,
                    base_delay=3.0,
                )
                log_gemini_inspection("generate_content", settings.auditor_model_id, res, {"role": "sre"})
                critique_text = getattr(res, "text", "") or ""
                if not critique_text.strip():
                    raise RuntimeError("SRE Auditor failed to generate evaluation rubric after retries.")
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

    from app.utils import extract_token_usage_dict
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
            **extract_token_usage_dict(res),
        },
    )
    state_dump = ctx.state.to_dict() if hasattr(ctx.state, "to_dict") else dict(ctx.state)
    yield Event(output=output_payload, custom_metadata={"state": state_dump, "sre_rubric": rubric.model_dump()})
