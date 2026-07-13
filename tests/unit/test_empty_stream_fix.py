from app.agents.performance.prompt import get_performance_prompt
from app.agents.security.prompt import get_security_prompt
from app.agents.sre.prompt import get_sre_prompt
from app.harness.tools import HarnessToolRegistry


def test_prompts_include_epistemic_facts_without_mandatory_tools(tmp_path):
    project_id = "proj_test_stream_fix"
    HarnessToolRegistry.add_verified_fact(project_id, "All microservices must use gRPC over TLS", verifier="SecurityAuditor")

    perf_prompt = get_performance_prompt(
        concept="Distributed Order Engine",
        current_round=1,
        history=[],
        project_id=project_id,
    )
    assert "All microservices must use gRPC over TLS" in perf_prompt
    assert "MANDATORY INSTRUCTION: Before proposing your design, you MUST call tool `query_verified_facts(project_id)`" not in perf_prompt

    sec_prompt = get_security_prompt(
        proposal="Use HTTP REST",
        project_id=project_id,
    )
    assert "All microservices must use gRPC over TLS" in sec_prompt

    sre_prompt = get_sre_prompt(
        proposal="Use HTTP REST",
        project_id=project_id,
    )
    assert "All microservices must use gRPC over TLS" in sre_prompt


def test_gemini_inspection_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.utils import log_gemini_inspection

    class DummyResponse:
        text = "sample text"
        candidates = []

    log_gemini_inspection("test_call", "gemini-3.5-flash", DummyResponse(), {"extra_key": "val"})

    client = TestClient(app)
    resp = client.get("/api/dev/gemini-inspection-logs?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert len(data["entries"]) > 0


def test_safety_finish_reason_guard():
    import pytest
    from app.utils import extract_stream_chunk_text

    class MockCandidate:
        finish_reason = "SAFETY"
        content = None

    class MockChunk:
        candidates = [MockCandidate()]

    with pytest.raises(RuntimeError, match="Stream interrupted by model safety/recitation guard"):
        extract_stream_chunk_text(MockChunk())


def test_truncate_prompt_text():
    from app.utils import truncate_prompt_text

    short_text = "hello world"
    assert truncate_prompt_text(short_text, max_chars=100) == short_text

    long_text = "A" * 1000 + "MIDDLE" + "Z" * 1000
    truncated = truncate_prompt_text(long_text, max_chars=200)
    assert len(truncated) < len(long_text)
    assert "TRUNCATED FOR CONTEXT WINDOW EFFICIENCY" in truncated
    assert truncated.startswith("A" * 100)
    assert truncated.endswith("Z" * 100)


def test_get_otel_spans_from_disk():
    from app.harness.tracing import DebateTracer
    from app.utils import FilesystemJail
    import json

    proj = "proj_test_otel_disk"
    s_data = {
        "span_id": "sp_123456",
        "project_id": proj,
        "span_name": "test_disk_span",
        "agent_role": "SecurityAuditor",
        "round_number": 1,
        "duration_ms": 120.5,
        "metadata": {"prompt_tokens": 1500, "completion_tokens": 200}
    }
    FilesystemJail.write_project_file(proj, "traces/sp_123456_test_disk_span.json", json.dumps(s_data))

    spans = DebateTracer.get_otel_spans(proj)
    assert len(spans) >= 1
    disk_span = next((s for s in spans if s["span_id"] == "sp_123456"), None)
    assert disk_span is not None
    assert disk_span["attributes"]["agent_role"] == "SecurityAuditor"
    assert disk_span["attributes"]["llm.prompt_tokens"] == 1500


