import pytest
from app.harness.moderator import (
    RoundManager,
    ContextSummarizer,
    should_exit_grill,
    should_synthesize_or_continue,
)
from app.types import DebateRound, PillarScores


def test_round_manager_termination():
    """Verify max rounds guard."""
    manager = RoundManager(max_rounds=3)
    assert not manager.should_terminate_debate(1)
    assert not manager.should_terminate_debate(2)
    assert manager.should_terminate_debate(3)
    assert manager.should_terminate_debate(4)


def test_context_summarizer_builds_agreement_matrix():
    """Verify AgreementMatrix extracts agreed points and contentions."""
    round1 = DebateRound(
        round_number=1,
        proposal_draft="- Architecture uses PostgreSQL\n- API Gateway pattern",
        critique="- Risk: high latency during replication",
        scores=PillarScores(
            performance=0.8,
            scalability=0.8,
            security=0.8,
            reliability=0.8,
            maintainability=0.8,
            cost_efficiency=0.8,
        ),
    )
    matrix = ContextSummarizer.build_agreement_matrix([round1])
    assert len(matrix.agreed_points) == 2
    assert len(matrix.active_contentions) == 1
    assert "PostgreSQL" in matrix.agreed_points[0]
    assert "latency" in matrix.active_contentions[0]


def test_routing_predicates():
    """Verify deterministic routing decisions."""
    scores_high = PillarScores(performance=0.9, scalability=0.9, security=0.9, reliability=0.9, maintainability=0.9, cost_efficiency=0.9)
    consensus, route = should_synthesize_or_continue(scores=scores_high, gate_threshold=0.85)
    assert consensus is True
    assert route == "synthesize"


class DummyContext:
    def __init__(self, state_dict=None):
        self.state = state_dict or {}
    def to_dict(self):
        return self.state


def test_initialize_debate_preserves_concept_on_resume():
    """Verify initialize_debate preserves existing concept during resume payload dispatch."""
    from app.harness.moderator import initialize_debate
    ctx = DummyContext({"concept": "I want to build an ai assisted IDE extension in French", "project_id": "proj_fr_ide"})
    resume_payload = {"grill_question": "Hybrid-Local model with Cloud Fallback."}

    event = initialize_debate._func(ctx, resume_payload)
    assert event.actions.route == "grill"
    assert ctx.state["concept"] == "I want to build an ai assisted IDE extension in French"
    assert ctx.state["project_id"] == "proj_fr_ide"


@pytest.mark.asyncio
async def test_grill_node_formats_past_history_and_question_number():
    """Verify grill_node injects past interview history and increments question numbers to prevent memory loss."""
    from app.harness.moderator import grill_node
    from app.config import settings

    settings.mock_mode = True
    ctx = DummyContext({
        "concept": "AI Tutor IDE Extension",
        "grill_question_count": 1,
        "max_grill_questions": 3,
        "grill_history": [
            {"role": "assistant", "content": "Question 1: Host IDE target?"},
            {"role": "user", "content": "VS Code"}
        ]
    })

    events = []
    async for ev in grill_node._func(ctx, "VS Code"):
        events.append(ev)

    assert ctx.state["grill_question_count"] == 2
    assert len(ctx.state["grill_history"]) == 4
    # Verify the assistant prompt formatted turn history correctly
    assert ctx.state["grill_history"][0]["content"] == "Question 1: Host IDE target?"


def test_context_summarizer_compact_round_history_and_contentions():
    from app.types import STRIDEThreatEntry, SREGapEntry
    long_proposal = "A" * 1200
    long_critique = "B" * 1200
    r1 = DebateRound(
        round_number=1,
        proposal_draft=long_proposal,
        critique=long_critique,
        scores=PillarScores(performance=0.8, scalability=0.8, security=0.8, reliability=0.8, maintainability=0.8, cost_efficiency=0.8),
    )
    compacted = ContextSummarizer.compact_round_history([r1])
    assert len(compacted) == 1
    assert len(compacted[0].proposal_draft) < len(long_proposal)
    assert "[Semantic Round Digest]" in compacted[0].proposal_draft or "Decisions:" in compacted[0].proposal_draft
    assert "[Semantic Critique Digest]" in compacted[0].critique or "Trade-offs:" in compacted[0].critique

    threats = [
        STRIDEThreatEntry(
            category="SPOOFING",
            threat_title="Spoof JWKS",
            component="Auth",
            severity="HIGH",
            status="OPEN",
            mitigation_status="Pending JWKS cache validation",
        )
    ]
    gaps = [
        SREGapEntry(
            category="SPOF",
            gap_title="Cross-region lock",
            component="DB",
            severity="HIGH",
            status="OPEN",
            remediation_status="Pending multi-region raft consensus",
        )
    ]
    matrix = ContextSummarizer.build_agreement_matrix([r1], open_threats=threats, open_gaps=gaps)
    assert any("Spoof JWKS" in c for c in matrix.active_contentions)
    assert any("Cross-region lock" in c for c in matrix.active_contentions)


