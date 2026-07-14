import asyncio
import logging
from pathlib import Path
from typing import Any

from google import genai
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.workflow import node
from google.genai import types

from app.agents.performance.prompt import get_performance_prompt
from app.config import settings
from app.types import DebateRound, DebateRoundEnvelope
from app.utils import (
    extract_interaction_id,
    extract_stream_chunk_text,
    load_matching_skills,
)

logger = logging.getLogger(__name__)

def get_genai_client() -> genai.Client:
    """Initializes and returns the Google Gen AI client based on configuration settings."""
    return settings.get_genai_client()


@node
async def performance_agent_node(ctx: Context, node_input: Any) -> Event:
    """
    Performance Architect Node.
    Analyzes scaling bottlenecks, latency profiles, and resource utilization.
    Invokes deterministic harness tools for pattern lookup and facts.
    Applies Left-Shifted DiagramSyntaxSensor validation and retry loop.
    """
    client = get_genai_client()
    history = ctx.state.get("rounds_history", [])
    current_round = ctx.state.get("current_round", 1)
    project_id = ctx.state.get("project_id", "default_project")
    concept = ctx.state.get("concept", "A new software project")
    proposal = ctx.state.get("proposal_draft") or (
        node_input if isinstance(node_input, str) and node_input.strip() and node_input.strip() != "None" else concept
    )

    judge_directive = ctx.state.get("latest_judge_directive", "")
    skills_dir = Path(__file__).parent / "skills"
    caveman_trigger = " caveman mode" if ctx.state.get("caveman_mode", True) else ""
    matched_skills = load_matching_skills(skills_dir, f"{proposal}{caveman_trigger}")

    from app.harness.moderator import ContextSummarizer
    from app.harness.tools import format_tools_for_interactions, get_harness_tools

    validated_history = [DebateRound.model_validate(r) if isinstance(r, dict) else r for r in history]
    compacted_history = ContextSummarizer.compact_round_history(validated_history)

    prompt = get_performance_prompt(
        proposal,
        current_round,
        compacted_history,
        judge_directive=judge_directive,
        skills_context=matched_skills,
        project_id=project_id
    )

    agreement_matrix = ContextSummarizer.extract_semantic_agreement(
        compacted_history,
        open_threats=ctx.state.get("open_threats", []),
        open_gaps=ctx.state.get("open_gaps", []),
    )
    prompt = (
        f"{prompt}\n\nExisting Agreement Matrix:\n{agreement_matrix.model_dump_json(indent=2)}"
    )

    harness_tools = get_harness_tools()

    previous_interaction_id = ctx.state.get("performance_interaction_id")
    proposal_text = ""
    res: Any = None

    if settings.mock_mode:
        proposal_text = f"### [MOCK MODE] Architectural Blueprint: {proposal} (Round {current_round})\n\n**1. High-Level Architecture**: Multi-region Kubernetes cluster running on Google Cloud with Global Load Balancing.\n**2. Database & Caching**: Cloud Spanner for global linearizability paired with Redis Cluster for sub-millisecond caching.\n**3. Performance Optimization**: Asynchronous task workers with Pub/Sub and CDN edge caching enabled.\n```mermaid\ngraph TD\nA[Client] --> B[Spanner]\n```"
        for line in proposal_text.splitlines(keepends=True):
            yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=line)]))
            await asyncio.sleep(0.05)
    else:
        max_retries = 2
        for attempt in range(max_retries + 1):
            proposal_text = ""
            try:
                response_stream = await client.aio.interactions.create(
                    model=settings.grill_model_id,
                    input=prompt,
                    tools=format_tools_for_interactions(harness_tools),
                    stream=True,
                    store=True,
                    previous_interaction_id=previous_interaction_id
                )
                from app.utils import log_gemini_inspection
                async for chunk in response_stream:
                    log_gemini_inspection("interactions.create_chunk", settings.grill_model_id, chunk, {"role": "performance"})
                    text = extract_stream_chunk_text(chunk)
                    if text:
                        proposal_text += text
                        yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))
                    chunk_id = extract_interaction_id(chunk)
                    if chunk_id:
                        ctx.state["performance_interaction_id"] = chunk_id
                if not proposal_text.strip():
                    raise ValueError("Empty stream returned from interactions API")
            except Exception as e:
                logger.warning(f"Interactions API failed for performance agent, falling back to stream_agent_with_tools: {e}")
                from app.harness.tools import stream_agent_with_tools
                async for text in stream_agent_with_tools(
                    client=client,
                    model_id=settings.grill_model_id,
                    prompt=prompt,
                    tools=harness_tools,
                ):
                    proposal_text += text
                    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))

            if not proposal_text.strip():
                logger.warning("Empty stream text for performance agent proposal, running non-streaming tool loop fallback.")
                from app.harness.tools import generate_content_with_tools
                proposal_text = await generate_content_with_tools(
                    client=client,
                    model_id=settings.grill_model_id,
                    prompt=prompt,
                    tools=harness_tools,
                    system_instruction=(
                        "You are the Lead Performance & Scaling Architect. Use your tools (`read_skill`, `lookup_architectural_pattern`, `query_verified_facts`) "
                        "and output a comprehensive, highly detailed markdown architectural proposal blueprint."
                    ),
                )
                if not proposal_text.strip():
                    raise RuntimeError("Lead Architect failed to generate architectural proposal blueprint after retries.")
                yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=proposal_text)]))

            # Check Left-Shifted sensor guardrails before accepting proposal
            envelope = DebateRoundEnvelope(proposal=proposal_text, round_number=current_round)
            from app.harness.ledger import EpistemicScratchpad
            from app.harness.sensors import LeftShiftedBlueprintPipeline
            scratchpad = EpistemicScratchpad.load(project_id)
            passed, backpressure_prompt, sensor_res = LeftShiftedBlueprintPipeline.enforce_sensor_guardrails(
                payload=envelope.model_dump(),
                project_id=project_id,
                epistemic_scratchpad=scratchpad,
            )
            if passed or attempt >= max_retries:
                break
            logger.info(f"Left-Shifted sensor failure on attempt {attempt+1}, auto-correcting with Harness backpressure.")
            prompt = f"{prompt}\n\n{backpressure_prompt}"

    ctx.state["latest_proposal"] = proposal_text
    envelope = DebateRoundEnvelope(
        proposal=proposal_text,
        round_number=current_round,
    )
    from app.harness.sensors import LeftShiftedBlueprintPipeline
    sensor_res = LeftShiftedBlueprintPipeline.run_pipeline(envelope.model_dump(), project_id=project_id)
    if not sensor_res.passed and sensor_res.formatted_backpressure:
        logger.warning(f"Sensor interception in proposal: {sensor_res.failed_layer}")
        envelope.metadata["sensor_result"] = sensor_res.model_dump()

    from app.utils import extract_token_usage_dict
    from app.harness.tracing import DebateTracer
    DebateTracer.record_span(
        ctx=ctx,
        span_name="AGENT_PROPOSAL_GENERATED",
        agent_role="Performance & Scaling Architect",
        round_number=current_round,
        metadata={"sensor_passed": sensor_res.passed, "proposal_chars": len(proposal_text), **extract_token_usage_dict(res)},
    )
    yield Event(output=envelope.model_dump(), custom_metadata={"state": ctx.state.to_dict()})

