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

