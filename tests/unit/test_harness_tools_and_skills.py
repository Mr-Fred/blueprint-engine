from pathlib import Path
import pytest

from app.harness.tools import HarnessToolRegistry
from app.harness.skills_registry import JITSkillRegistry
from app.harness.moderator import ContextSummarizer, AgreementMatrix
from app.harness.sensors import LeftShiftedBlueprintPipeline
from app.types import DebateRound, PillarScores


def test_harness_tool_registry():
    # Architectural pattern lookup
    pattern = HarnessToolRegistry.lookup_architectural_pattern("event_sourcing")
    assert "Immutable append-only domain events" in pattern

    # OWASP Stride check
    stride = HarnessToolRegistry.check_owasp_stride_vector("spoofing")
    assert "Authentication bypass" in stride

    # Compliance checklist
    comp = HarnessToolRegistry.check_compliance_checklist("gdpr")
    assert isinstance(comp, list) or "gdpr" in str(comp).lower()

    # Verified facts manipulation
    res = HarnessToolRegistry.add_verified_fact("proj_test", "Spanner is multi-region", "tester")
    assert res.get("event_type") == "EpistemicFactAdded"
    facts = HarnessToolRegistry.query_verified_facts("proj_test")
    assert any("Spanner is multi-region" in f.get("statement", "") for f in facts)


def test_jit_skill_registry(tmp_path):
    skill_file = tmp_path / "test-skill.md"
    skill_file.write_text(
        "---\n"
        "name: test-skill\n"
        "description: Useful testing skill for validation\n"
        "---\n"
        "# Test Skill\n\nInstructions here.",
        encoding="utf-8",
    )

    catalog = JITSkillRegistry.get_skills_catalog(tmp_path)
    assert "test-skill" in catalog
    assert "Useful testing skill for validation" in catalog

    loaded = JITSkillRegistry.read_skill("test-skill", tmp_path)
    assert "# Test Skill" in loaded
    assert "Instructions here." in loaded

    search_res = JITSkillRegistry.search_skills("validation", tmp_path)
    assert len(search_res) == 1
    assert search_res[0]["name"] == "test-skill"


def test_moderator_semantic_agreement():
    rounds = [
        DebateRound(
            round_number=1,
            proposal_draft="- Use Kubernetes\n- Use Spanner",
            critique="- Latency risk in cross-region Spanner transactions",
            scores=PillarScores(performance=0.8, scalability=0.8, security=0.8, reliability=0.8, maintainability=0.8, cost_efficiency=0.8),
        )
    ]

    matrix = ContextSummarizer.extract_semantic_agreement(rounds)
    assert isinstance(matrix, AgreementMatrix)
    assert "Use Kubernetes" in matrix.agreed_points or len(matrix.agreed_points) > 0


def test_enforce_sensor_guardrails():
    payload_clean = {
        "round_number": 1,
        "proposal": "Clean proposal with syntax diagram ```mermaid\ngraph TD\nA-->B\n```",
    }
    passed, prompt, res = LeftShiftedBlueprintPipeline.enforce_sensor_guardrails(payload_clean, project_id="test_sensor_clean")
    assert passed is True
    assert prompt is None
    assert res.passed is True


def test_format_tools_for_interactions():
    from app.harness.tools import format_tools_for_interactions, HarnessToolRegistry
    formatted = format_tools_for_interactions([HarnessToolRegistry.lookup_architectural_pattern])
    assert len(formatted) == 1
    assert formatted[0]["type"] == "function"
    assert formatted[0]["name"] == "lookup_architectural_pattern"
    assert "looks up" in formatted[0]["description"].lower()


def test_stream_chunk_extraction_and_standalone_tools():
    from types import SimpleNamespace
    from app.utils import extract_stream_chunk_text
    from app.harness.tools import get_harness_tools, format_tools_for_interactions

    # Test StepDelta SSE chunk with delta.text
    chunk_sse = SimpleNamespace(delta=SimpleNamespace(text="Hello world"))
    assert extract_stream_chunk_text(chunk_sse) == "Hello world"

    # Test direct text chunk
    chunk_direct = SimpleNamespace(text="Direct text")
    assert extract_stream_chunk_text(chunk_direct) == "Direct text"

    # Test dict chunk
    assert extract_stream_chunk_text({"text": "Dict text"}) == "Dict text"
    assert extract_stream_chunk_text("String chunk") == "String chunk"

    # Test candidates chunk
    chunk_cand = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(text="Candidate text")]))])
    assert extract_stream_chunk_text(chunk_cand) == "Candidate text"

    # Test standalone harness tools are callable functions
    tools = get_harness_tools()
    assert len(tools) >= 5
    for t in tools:
        assert callable(t)
        assert not hasattr(t, "__self__")  # Ensure not a bound method

    formatted = format_tools_for_interactions(tools)
    assert len(formatted) == len(tools)
    for ft in formatted:
        assert ft["type"] == "function"




