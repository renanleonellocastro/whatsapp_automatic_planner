"""Workflow domain: request lifecycle state machine and its vocabulary."""

from wapp_planner.workflow.enums import Intent, MessageType, RequestState, Trigger
from wapp_planner.workflow.state_machine import (
    TERMINAL_STATES,
    IllegalTransitionError,
    is_terminal,
    next_state,
)
from wapp_planner.workflow.triggers import trigger_for

__all__ = [
    "Intent",
    "MessageType",
    "RequestState",
    "Trigger",
    "IllegalTransitionError",
    "TERMINAL_STATES",
    "is_terminal",
    "next_state",
    "trigger_for",
]
