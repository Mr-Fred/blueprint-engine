import pytest
from app.types import DebateState

def test_debate_state_declares_all_required_keys():
    """Verify that DebateState declares all keys assigned to ctx.state across agents."""
    schema_fields = set(DebateState.model_fields.keys())
    
    required_state_keys = {
        "project_id",
        "concept",
        "current_round",
        "rounds_history",
        "grill_history",
        "grill_completed",
        "consensus_achieved",
        "final_prd",
        "final_architecture",
        "latest_proposal",
        "latest_judge_directive",
        "force_synthesis_flag",
        "caveman_mode",
        "grill_interaction_id",
        "grill_question_count",
        "performance_interaction_id",
        "security_interaction_id",
        "sre_interaction_id",
    }
    
    missing_keys = required_state_keys - schema_fields
    assert not missing_keys, f"DebateState schema is missing declared fields: {missing_keys}"
