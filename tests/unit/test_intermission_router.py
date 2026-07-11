import pytest
from app.harness.intermission import (
    IntermissionBranch,
    IntermissionDirective,
    IntermissionRouter,
)


def test_parse_input_dict():
    raw = {"action": "STEER", "steering_note": "Please use Redis for caching."}
    directive = IntermissionRouter.parse_input(raw)
    assert directive.action == IntermissionBranch.STEER
    assert directive.steering_note == "Please use Redis for caching."
    assert IntermissionRouter.resolve_target_node(directive) == "performance_agent_node"


def test_parse_input_string_keywords():
    directive_synth = IntermissionRouter.parse_input("FORCE_SYNTHESIZE")
    assert directive_synth.action == IntermissionBranch.FORCE_SYNTHESIZE
    assert IntermissionRouter.resolve_target_node(directive_synth) == "synthesis_node"

    directive_cancel = IntermissionRouter.parse_input("CANCEL")
    assert directive_cancel.action == IntermissionBranch.CANCEL
    assert IntermissionRouter.resolve_target_node(directive_cancel) == "CANCELLED"


def test_parse_input_string_steering_note():
    directive = IntermissionRouter.parse_input("Make sure to encrypt backups")
    assert directive.action == IntermissionBranch.STEER
    assert directive.steering_note == "Make sure to encrypt backups"
