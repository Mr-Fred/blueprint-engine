from types import SimpleNamespace
from app.harness.tracing import DebateTracer, TraceSpan


def test_debate_tracer_record_span_and_retrieve():
    ctx = SimpleNamespace(state={"project_id": "proj_trace_test", "journey_trace": []})

    span1 = DebateTracer.record_span(
        ctx=ctx,
        span_name="PHASE_1_GRILL_TURN",
        agent_role="Moderator",
        metadata={"question_count": 1},
    )

    span2 = DebateTracer.record_span(
        ctx=ctx,
        span_name="PHASE_2_ROUND_START",
        agent_role="Performance Architect",
        round_number=1,
        duration_ms=124.5,
        metadata={"sensor_passed": True},
    )

    assert isinstance(span1, TraceSpan)
    assert span1.project_id == "proj_trace_test"
    assert span1.span_name == "PHASE_1_GRILL_TURN"

    journey = DebateTracer.get_journey_trace(ctx)
    assert len(journey) == 2
    assert journey[0]["span_name"] == "PHASE_1_GRILL_TURN"
    assert journey[1]["span_name"] == "PHASE_2_ROUND_START"
    assert journey[1]["round_number"] == 1
    assert journey[1]["duration_ms"] == 124.5


def test_debate_tracer_otel_spans():
    ctx = SimpleNamespace(state={"project_id": "proj_otel_test", "journey_trace": []})
    DebateTracer.record_span(
        ctx=ctx,
        span_name="OTEL_TEST_SPAN",
        agent_role="LeadArchitect",
        round_number=2,
        duration_ms=45.0,
        metadata={"verified_facts_checked": True},
    )

    otel_spans = DebateTracer.get_otel_spans("proj_otel_test")
    assert len(otel_spans) >= 1
    names = [s["name"] for s in otel_spans]
    assert "OTEL_TEST_SPAN" in names
