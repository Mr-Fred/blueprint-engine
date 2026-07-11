import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("debate.tracer")


class TraceSpan(BaseModel):
    """Structured span representing a milestone in the debate progress or user journey."""
    span_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    span_name: str
    agent_role: str
    round_number: Optional[int] = None
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DebateTracer:
    """End-to-end telemetry and tracing recorder for MAD Engine debate workflows."""

    @staticmethod
    def record_span(
        ctx: Any,
        span_name: str,
        agent_role: str,
        round_number: Optional[int] = None,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceSpan:
        """
        Records a structured TraceSpan into ctx.state['journey_trace'] and persists to jail trace log.
        """
        project_id = "default_proj"
        if hasattr(ctx, "state") and isinstance(ctx.state, dict):
            project_id = ctx.state.get("project_id", project_id)
        elif hasattr(ctx, "state") and hasattr(ctx.state, "get"):
            project_id = ctx.state.get("project_id", project_id)

        span = TraceSpan(
            project_id=project_id,
            span_name=span_name,
            agent_role=agent_role,
            round_number=round_number,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

        logger.info(
            f"[TRACE {span.span_name}] project={project_id} role='{agent_role}' "
            f"round={round_number} duration={duration_ms}ms meta_keys={list(span.metadata.keys())}"
        )

        if hasattr(ctx, "state") and isinstance(ctx.state, dict):
            journey = ctx.state.get("journey_trace") or []
            journey.append(span.model_dump())
            ctx.state["journey_trace"] = journey
        elif hasattr(ctx, "state") and hasattr(ctx.state, "__setitem__"):
            journey = ctx.state.get("journey_trace", []) or []
            journey.append(span.model_dump())
            ctx.state["journey_trace"] = journey

        # Persist append-only log to project jail
        try:
            from app.utils import FilesystemJail
            trace_line = json.dumps(span.model_dump())
            FilesystemJail.write_file(project_id, f"traces/{span.span_id}_{span.span_name}.json", trace_line)
        except Exception as e:
            logger.debug(f"Could not write trace file to jail: {e}")

        return span

    @staticmethod
    def get_journey_trace(ctx: Any) -> List[Dict[str, Any]]:
        """Retrieves the full chronological journey trace from context state."""
        if hasattr(ctx, "state"):
            if isinstance(ctx.state, dict):
                return ctx.state.get("journey_trace", [])
            elif hasattr(ctx.state, "get"):
                return ctx.state.get("journey_trace", [])
        return []
