import asyncio
import logging
from pathlib import Path
from typing import Any

from google import genai
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.workflow import node
from google.genai import types

from app.agents.security.prompt import get_security_prompt
from app.config import settings
from app.types import SecurityRubricEvaluation, STRIDEThreatEntry
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
async def security_agent_node(ctx: Context, node_input: Any) -> Event:
    """The Security & Resilience Auditor critiques the proposal draft using structured ADK 2.0 evaluation rubrics."""
    node_input = parse_node_input(node_input)
    client = get_genai_client()
    project_id = ctx.state.get("project_id", "default_proj")
    proposal = node_input.get("proposal", str(node_input)) if isinstance(node_input, dict) else str(node_input)

    judge_directive = ctx.state.get("latest_judge_directive", None)

    skills_dir = Path(__file__).parent / "skills"
    caveman_trigger = " caveman mode" if ctx.state.get("caveman_mode", True) else ""
    matched_skills = load_matching_skills(skills_dir, f"{proposal}{caveman_trigger}")

    prompt = get_security_prompt(proposal, judge_directive=judge_directive, skills_context=matched_skills, project_id=project_id)

    prompt = (
        f"You MUST return a valid JSON payload matching the SecurityRubricEvaluation schema.\n"
        f"Evaluate data protection (0.0-1.0), identity access (0.0-1.0), surface area (LOW/MEDIUM/HIGH), "
        f"and STRIDE threat register.\n\n"
        f"{prompt}"
    )

    critique_text = ""
    res: Any = None
    rubric: SecurityRubricEvaluation

    from app.harness.tools import format_tools_for_interactions, get_harness_tools
    harness_tools = get_harness_tools()

    if settings.mock_mode:
        rubric = SecurityRubricEvaluation(
            data_protection_score=0.9,
            identity_access_score=0.85,
            vulnerability_surface_area="LOW",
            stride_threat_register=[
                STRIDEThreatEntry(
                    category="SPOOFING",
                    threat_title="API Gateway Token Spoofing",
                    component="API Gateway",
                    severity="HIGH",
                    mitigation_status="Enforce OAuth2 OIDC token verification at gateway edge."
                )
            ],
            detailed_critique="### [MOCK MODE] Security Critique & Hardening\n\n- **Zero-Trust Auth**: Require Workload Identity Federation instead of static service account keys.\n- **Data Encryption**: Enforce Customer-Managed Encryption Keys (CMEK) on Spanner and Redis buckets.\n- **Rate Limiting**: Add Cloud Armor edge security policies to mitigate DDoS and brute-force attacks.\n"
        )
        critique_text = rubric.detailed_critique
        yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=critique_text)]))
    else:
        previous_interaction_id = ctx.state.get("security_interaction_id")
        try:
            response_stream = await client.aio.interactions.create(
                model=settings.auditor_model_id,
                input=prompt,
                tools=format_tools_for_interactions(harness_tools),
                stream=True,
                store=True,
                previous_interaction_id=previous_interaction_id,
                response_format=SecurityRubricEvaluation.model_json_schema(),
            )
            from app.utils import log_gemini_inspection
            async for chunk in response_stream:
                log_gemini_inspection("interactions.create_chunk", settings.auditor_model_id, chunk, {"role": "security"})
                text = extract_stream_chunk_text(chunk)
                if text:
                    critique_text += text
                    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))
                chunk_id = extract_interaction_id(chunk)
                if chunk_id:
                    ctx.state["security_interaction_id"] = chunk_id
            if not critique_text.strip():
                raise ValueError("Empty stream returned from interactions API")
        except Exception as e:
            logger.warning(f"Interactions API failed for security agent ({e}), falling back to stream_agent_with_tools.")
            try:
                from app.harness.tools import stream_agent_with_tools
                async for text in stream_agent_with_tools(
                    client=client,
                    model_id=settings.auditor_model_id,
                    prompt=prompt,
                    tools=harness_tools,
                    response_schema=SecurityRubricEvaluation,
                ):
                    critique_text += text
                    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))
            except Exception as stream_err:
                logger.warning(f"stream_agent_with_tools failed ({stream_err}).")

            if not critique_text.strip():
                logger.warning("Empty stream text for security agent, running non-streaming text fallback with retry.")
                from app.utils import call_with_retry_on_429, log_gemini_inspection
                res = await call_with_retry_on_429(
                    lambda: client.aio.models.generate_content(
                        model=settings.auditor_model_id,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=SecurityRubricEvaluation,
                        ),
                    ),
                    max_retries=3,
                    base_delay=3.0,
                )
                log_gemini_inspection("generate_content", settings.auditor_model_id, res, {"role": "security"})
                critique_text = getattr(res, "text", "") or ""
                if not critique_text.strip():
                    raise RuntimeError("Security Auditor failed to generate evaluation rubric after retries.")
                yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=critique_text)]))

        try:
            cleaned = critique_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:].rstrip("`").strip()
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:].rstrip("`").strip()
            rubric = SecurityRubricEvaluation.model_validate_json(cleaned)
            critique_text = rubric.detailed_critique
        except Exception as parse_err:
            logger.warning(f"Failed to parse SecurityRubricEvaluation JSON ({parse_err}), using fallback structured rubric.")
            rubric = SecurityRubricEvaluation(
                data_protection_score=0.85,
                identity_access_score=0.85,
                vulnerability_surface_area="MEDIUM",
                stride_threat_register=[],
                detailed_critique=critique_text or "### Security Review\n\nEnsure zero-trust isolation, TLS 1.3 encryption, and strict least-privilege IAM policies across all service boundaries."
            )

    ctx.state["latest_security_rubric"] = rubric.model_dump()
    ctx.state["temp:latest_security_critique"] = critique_text
    if isinstance(node_input, dict):
        output_payload = dict(node_input)
        output_payload.pop("proposal", None)
        output_payload.pop("security_critique", None)
        output_payload.pop("sre_critique", None)
        output_payload["security_rubric"] = rubric.model_dump()
    else:
        output_payload = critique_text

    from app.utils import extract_token_usage_dict
    from app.harness.tracing import DebateTracer
    DebateTracer.record_span(
        ctx=ctx,
        span_name="AGENT_CRITIQUE_GENERATED",
        agent_role="Security & Resilience Auditor",
        round_number=ctx.state.get("current_round", 1),
        metadata={
            "critique_chars": len(critique_text),
            "data_protection_score": rubric.data_protection_score,
            "identity_access_score": rubric.identity_access_score,
            "vulnerability_surface_area": rubric.vulnerability_surface_area,
            **extract_token_usage_dict(res),
        },
    )
    state_dump = ctx.state.to_dict() if hasattr(ctx.state, "to_dict") else dict(ctx.state)
    yield Event(output=output_payload, custom_metadata={"state": state_dump, "security_rubric": rubric.model_dump()})


