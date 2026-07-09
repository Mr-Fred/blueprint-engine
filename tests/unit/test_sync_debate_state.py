import pytest
from pydantic import BaseModel
from app.main import sync_debate_state_from_event, DEBATE_SESSIONS
from app.types import DebateState, DebateRound, PillarScores

class DummyEvent(BaseModel):
    custom_metadata: dict

def test_sync_debate_state_preserves_rounds_history_from_state_update():
    project_id = "test_sync_proj"
    DEBATE_SESSIONS[project_id] = DebateState(
        project_id=project_id,
        concept="Test Concept",
        current_round=1,
        rounds_history=[]
    )

    sample_round = DebateRound(
        round_number=1,
        proposal_draft="Proposal Text",
        critique="Critique Text",
        scores=PillarScores(
            performance=0.9,
            scalability=0.9,
            security=0.9,
            reliability=0.9,
            maintainability=0.9,
            cost_efficiency=0.9
        ),
        judge_directive=None
    )

    event = DummyEvent(
        custom_metadata={
            "state": {
                "current_round": 2,
                "rounds_history": [sample_round.model_dump()],
                "consensus_achieved": True
            }
        }
    )

    sync_debate_state_from_event(project_id, event)
    assert len(DEBATE_SESSIONS[project_id].rounds_history) == 1
    assert DEBATE_SESSIONS[project_id].rounds_history[0].proposal_draft == "Proposal Text"
    assert DEBATE_SESSIONS[project_id].rounds_history[0].scores.performance == 0.9

    # Second event during next turn stream where state_update might not have full rounds_history
    empty_event = DummyEvent(
        custom_metadata={
            "state": {
                "current_round": 2,
            }
        }
    )
    sync_debate_state_from_event(project_id, empty_event)
    assert len(DEBATE_SESSIONS[project_id].rounds_history) == 1, "Should not wipe out existing rounds_history"
