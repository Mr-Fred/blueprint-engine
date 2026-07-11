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
from app.shared_state import ACTIVE_DIRECTIVES
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

    judge_directive = ACTIVE_DIRECTIVES.get(project_id) or ctx.state.get("latest_judge_directive", None)

    skills_dir = Path(__file__).parent / "skills"
    caveman_trigger = " caveman mode" if ctx.state.get("caveman_mode", True) else ""
    matched_skills = load_matching_skills(skills_dir, f"{proposal}{caveman_trigger}")

    prompt = get_security_prompt(proposal, judge_directive=judge_directive, skills_context=matched_skills)

    prompt = (
        f"You MUST return a valid JSON payload matching the SecurityRubricEvaluation schema.\n"
        f"Evaluate data protection (0.0-1.0), identity access (0.0-1.0), surface area (LOW/MEDIUM/HIGH), "
        f"and STRIDE threat register.\n\n"
        f"{prompt}"
    )

    critique_text = ""
    rubric: SecurityRubricEvaluation

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
                stream=True,
                store=True,
                previous_interaction_id=previous_interaction_id,
                response_format=SecurityRubricEvaluation,
            )
            async for chunk in response_stream:
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
            logger.warning(f"Interactions API failed for security agent ({e}), falling back to generate_content_stream.")
            try:
                response_stream = await client.aio.models.generate_content_stream(
                    model=settings.auditor_model_id,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=SecurityRubricEvaluation,
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
                        response_schema=SecurityRubricEvaluation,
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
        output_payload["security_critique"] = critique_text
        output_payload["security_rubric"] = rubric.model_dump()
    else:
        output_payload = critique_text

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
        },
    )
    state_dump = ctx.state.to_dict() if hasattr(ctx.state, "to_dict") else dict(ctx.state)
    yield Event(output=output_payload, custom_metadata={"state": state_dump, "security_rubric": rubric.model_dump()})


