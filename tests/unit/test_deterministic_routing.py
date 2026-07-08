import pytest

from app.agents.judge.agent import should_synthesize_or_continue
from app.agents.performance.agent import should_exit_grill
from app.types import PillarScores


class MockContext:
    def __init__(self):
        self.state = {}


def test_should_exit_grill():
    ctx = MockContext()

    # 1. Normal active interview should continue
    assert should_exit_grill(ctx, user_answer="My concurrent load is 10k", question_count=1, max_questions=3) is False

    # 2. Exits when grill_completed state flag is set
    ctx.state["grill_completed"] = True
    assert should_exit_grill(ctx, question_count=1, max_questions=3) is True
    ctx.state["grill_completed"] = False

    # 3. Exits when current_round > 1
    ctx.state["current_round"] = 2
    assert should_exit_grill(ctx, question_count=1, max_questions=3) is True
    ctx.state["current_round"] = 1

    # 4. Exits when user requests skip
    assert should_exit_grill(ctx, user_answer="SKIP_INTERVIEW", question_count=1, max_questions=3) is True

    # 5. Exits when max questions reached
    assert should_exit_grill(ctx, question_count=3, max_questions=3) is True

    # 6. Exits when model output starts with READY
    assert should_exit_grill(ctx, question_count=1, max_questions=3, model_output="READY") is True


def test_should_synthesize_or_continue():
    # 1. User explicit choices during HITL review
    assert should_synthesize_or_continue(user_choice="SYNTHESIZE") == (True, "synthesize")
    assert should_synthesize_or_continue(user_choice="CONTINUE") == (False, "continue")
    assert should_synthesize_or_continue(user_choice="Please focus on Redis caching") == (False, "continue")

    # 2. Scores meet threshold
    high_scores = PillarScores(
        performance=0.9,
        scalability=0.9,
        security=0.9,
        reliability=0.9,
        maintainability=0.9,
        cost_efficiency=0.9,
    )
    assert should_synthesize_or_continue(
        scores=high_scores, current_round=1, max_rounds=3, gate_threshold=0.85
    ) == (True, "synthesize")

    # 3. Scores below threshold but max rounds reached
    low_scores = PillarScores(
        performance=0.6,
        scalability=0.6,
        security=0.6,
        reliability=0.6,
        maintainability=0.6,
        cost_efficiency=0.6,
    )
    assert should_synthesize_or_continue(
        scores=low_scores, current_round=3, max_rounds=3, gate_threshold=0.85
    ) == (True, "synthesize")

    # 4. Scores below threshold and rounds remaining -> route to review
    assert should_synthesize_or_continue(
        scores=low_scores, current_round=1, max_rounds=3, gate_threshold=0.85
    ) == (False, "review")
