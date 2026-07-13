import json
import logging
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class IntermissionBranch(StrEnum):
    """The 4 deterministic HITL Intermission actions."""
    STEER = "STEER"
    CONTINUE = "CONTINUE"
    FORCE_SYNTHESIZE = "FORCE_SYNTHESIZE"
    CANCEL = "CANCEL"


class IntermissionDirective(BaseModel):
    """Structured HITL directive parsed from intermission resume input."""
    action: IntermissionBranch = Field(default=IntermissionBranch.CONTINUE, description="Branch choice")
    steering_note: str | None = Field(None, description="Human steering instructions if action is STEER")


class IntermissionRouter:
    """
    Parses human intermission input and routes the debate state machine cleanly across 4 branches:
    - STEER: Inject steering note into context and resume round debate (`performance_agent_node`).
    - CONTINUE: Resume next turn without intervention (`performance_agent_node`).
    - FORCE_SYNTHESIZE: Immediately short-circuit debate and enter synthesis (`synthesis_node`).
    - CANCEL: Terminate the debate stream safely.
    """

    @classmethod
    def parse_input(cls, raw_input: Any) -> IntermissionDirective:
        """Parses string or dictionary input into a typed IntermissionDirective."""
        if isinstance(raw_input, IntermissionDirective):
            return raw_input
        if isinstance(raw_input, dict):
            action_str = raw_input.get("action", "CONTINUE").upper()
            note = raw_input.get("steering_note") or raw_input.get("note")
            return cls._to_directive(action_str, note)
        if isinstance(raw_input, str):
            # Check if JSON encoded string
            trimmed = raw_input.strip()
            if trimmed.startswith("{") and trimmed.endswith("}"):
                try:
                    data = json.loads(trimmed)
                    return cls.parse_input(data)
                except Exception:
                    pass
            # Check keywords
            upper_raw = trimmed.upper()
            if upper_raw in ("FORCE_SYNTHESIZE", "SYNTHESIZE"):
                return IntermissionDirective(action=IntermissionBranch.FORCE_SYNTHESIZE)
            if upper_raw in ("CANCEL", "ABORT"):
                return IntermissionDirective(action=IntermissionBranch.CANCEL)
            if upper_raw in ("CONTINUE", "NEXT"):
                return IntermissionDirective(action=IntermissionBranch.CONTINUE)
            # If plain text with instructions, treat as STEER
            return IntermissionDirective(action=IntermissionBranch.STEER, steering_note=trimmed)
        return IntermissionDirective(action=IntermissionBranch.CONTINUE)

    @staticmethod
    def _to_directive(action_str: str, note: str | None) -> IntermissionDirective:
        try:
            branch = IntermissionBranch(action_str)
        except ValueError:
            branch = IntermissionBranch.CONTINUE
        return IntermissionDirective(action=branch, steering_note=note)

    @classmethod
    def resolve_target_node(cls, directive: IntermissionDirective) -> str:
        """Determines the target ADK workflow node based on the IntermissionDirective."""
        if directive.action == IntermissionBranch.FORCE_SYNTHESIZE:
            return "synthesis_node"
        if directive.action == IntermissionBranch.CANCEL:
            return "CANCELLED"
        # Both STEER and CONTINUE proceed to next round debate
        return "performance_agent_node"
