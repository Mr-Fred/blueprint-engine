import json
import logging
import time
import uuid
from datetime import UTC, datetime, timezone
from typing import Any, Dict, List

from pydantic import BaseModel, Field

logger = logging.getLogger("debate.tracer")

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    OTEL_AVAILABLE = True
except ImportError as e:
    OTEL_AVAILABLE = False
    logger.warning(f"OpenTelemetry SDK not installed ({e}), using lightweight fallback for traces.")

# Global singleton InMemorySpanExporter for serving UI traces on demand
_in_memory_exporter: Any | None = None
_tracer_provider: Any | None = None


def setup_otel_provider():
    """Initializes the OpenTelemetry TracerProvider and registers an InMemorySpanExporter."""
    global _in_memory_exporter, _tracer_provider
    if not OTEL_AVAILABLE:
        return None
    if _tracer_provider is None:
        _tracer_provider = TracerProvider()
        _in_memory_exporter = InMemorySpanExporter()
        _tracer_provider.add_span_processor(SimpleSpanProcessor(_in_memory_exporter))
        trace.set_tracer_provider(_tracer_provider)
    return trace.get_tracer("mad_engine_harness")


class TraceSpan(BaseModel):
    """Structured span representing a milestone in the debate progress or user journey."""
    span_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    span_name: str
    agent_role: str
    round_number: int | None = None
    duration_ms: float | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DebateTracer:
    """End-to-end telemetry and OpenTelemetry tracing recorder for MAD Engine debate workflows."""

    @staticmethod
    def record_span(
        ctx: Any,
        span_name: str,
        agent_role: str,
        round_number: int | None = None,
        duration_ms: float | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> TraceSpan:
        """
        Records an OpenTelemetry span via OTel SDK, persists to sandboxed project file exporter,
        and maintains state for UI trace inspection.
        """
        project_id = "default_proj"
        if hasattr(ctx, "state") and isinstance(ctx.state, dict):
            project_id = ctx.state.get("project_id", project_id)
        elif hasattr(ctx, "state") and hasattr(ctx.state, "get"):
            project_id = ctx.state.get("project_id", project_id)

        meta = metadata or {}
        tracer = setup_otel_provider()

        span_obj = TraceSpan(
            project_id=project_id,
            span_name=span_name,
            agent_role=agent_role,
            round_number=round_number,
            duration_ms=duration_ms,
            metadata=meta,
        )

        if tracer and OTEL_AVAILABLE:
            with tracer.start_as_current_span(span_name) as otel_span:
                otel_span.set_attribute("project_id", project_id)
                otel_span.set_attribute("agent_role", agent_role)
                otel_span.set_attribute("gen_ai.system", "gemini")
                otel_span.set_attribute("gen_ai.operation.name", span_name)
                if round_number is not None:
                    otel_span.set_attribute("round_number", round_number)
                if duration_ms is not None:
                    otel_span.set_attribute("duration_ms", float(duration_ms))
                for k, v in meta.items():
                    if k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                        otel_span.set_attribute(f"llm.{k}", int(v))
                        otel_span.set_attribute(f"gen_ai.usage.{k}", int(v))
                    if isinstance(v, (str, int, float, bool)):
                        otel_span.set_attribute(f"metadata.{k}", v)
                    else:
                        otel_span.set_attribute(f"metadata.{k}", json.dumps(v))

        logger.info(
            f"[OTEL TRACE {span_obj.span_name}] project={project_id} role='{agent_role}' "
            f"round={round_number} duration={duration_ms}ms meta_keys={list(meta.keys())}"
        )

        if hasattr(ctx, "state") and isinstance(ctx.state, dict):
            journey = ctx.state.get("journey_trace") or []
            journey.append(span_obj.model_dump())
            ctx.state["journey_trace"] = journey
        elif hasattr(ctx, "state") and hasattr(ctx.state, "__setitem__"):
            journey = ctx.state.get("journey_trace", []) or []
            journey.append(span_obj.model_dump())
            ctx.state["journey_trace"] = journey

        # Persist append-only OTel span log to project jail
        try:
            from app.utils import FilesystemJail
            trace_line = json.dumps(span_obj.model_dump())
            FilesystemJail.write_project_file(project_id, f"traces/{span_obj.span_id}_{span_obj.span_name}.json", trace_line)
        except Exception as e:
            logger.debug(f"Could not write trace file to jail: {e}")

        return span_obj

    @staticmethod
    def get_journey_trace(ctx: Any) -> List[Dict[str, Any]]:
        """Retrieves the full chronological journey trace from context state."""
        if hasattr(ctx, "state"):
            if isinstance(ctx.state, dict):
                return ctx.state.get("journey_trace", [])
            elif hasattr(ctx.state, "get"):
                return ctx.state.get("journey_trace", [])
        return []

    @staticmethod
    def get_otel_spans(project_id: str | None = None) -> List[Dict[str, Any]]:
        """Retrieves serialized OpenTelemetry spans from the InMemorySpanExporter and disk storage for UI display."""
        spans_out = []
        seen_ids = set()

        if _in_memory_exporter and OTEL_AVAILABLE:
            for span in _in_memory_exporter.get_finished_spans():
                attrs = dict(span.attributes or {})
                if project_id and attrs.get("project_id") != project_id:
                    continue
                span_id_hex = format(span.context.span_id, "016x") if span.context else "unknown"
                seen_ids.add(span_id_hex)
                spans_out.append({
                    "span_id": span_id_hex,
                    "trace_id": format(span.context.trace_id, "032x") if span.context else "unknown",
                    "name": span.name,
                    "attributes": attrs,
                    "start_time_ns": span.start_time,
                    "end_time_ns": span.end_time,
                })

        if project_id:
            try:
                from app.utils import FilesystemJail
                traces_dir = FilesystemJail.get_project_dir(project_id) / "traces"
                if traces_dir.exists() and traces_dir.is_dir():
                    for f in sorted(traces_dir.glob("*.json")):
                        try:
                            s_data = json.loads(f.read_text(encoding="utf-8"))
                            span_id = s_data.get("span_id", "unknown")
                            if span_id in seen_ids:
                                continue
                            seen_ids.add(span_id)
                            meta = s_data.get("metadata") or {}
                            attrs = {
                                "project_id": s_data.get("project_id", project_id),
                                "agent_role": s_data.get("agent_role", "system"),
                                "gen_ai.system": "gemini",
                                "gen_ai.operation.name": s_data.get("span_name", "unknown_span"),
                            }
                            if s_data.get("round_number") is not None:
                                attrs["round_number"] = s_data.get("round_number")
                            if s_data.get("duration_ms") is not None:
                                attrs["duration_ms"] = float(s_data["duration_ms"])
                            for mk, mv in meta.items():
                                attrs[f"metadata.{mk}"] = mv
                                if mk in ("prompt_tokens", "completion_tokens", "total_tokens"):
                                    attrs[f"llm.{mk}"] = int(mv)
                                    attrs[f"gen_ai.usage.{mk}"] = int(mv)
                            spans_out.append({
                                "span_id": span_id,
                                "trace_id": s_data.get("trace_id", "00000000000000000000000000000000"),
                                "name": s_data.get("span_name", "unknown_span"),
                                "attributes": attrs,
                                "start_time_ns": 0,
                                "end_time_ns": int(float(s_data.get("duration_ms", 0)) * 1e6) if s_data.get("duration_ms") else 0,
                            })
                        except Exception:
                            continue
            except Exception:
                pass

        return spans_out

