"""Map an owner decision to the state-machine trigger it fires (§6)."""

from __future__ import annotations

from typing import Final

from wapp_planner.domain.enums import OwnerDecision
from wapp_planner.workflow.enums import Trigger

_DECISION_TRIGGER: Final[dict[OwnerDecision, Trigger]] = {
    OwnerDecision.CONFIRM: Trigger.OWNER_CONFIRMED,
    OwnerDecision.CORRECT: Trigger.OWNER_CORRECTED,
    OwnerDecision.REJECT: Trigger.OWNER_REJECTED,
    OwnerDecision.APPROVE: Trigger.OWNER_APPROVED,
    OwnerDecision.REVISE: Trigger.OWNER_REQUESTED_REVISION,
}


def trigger_for(decision: OwnerDecision) -> Trigger:
    """Return the :class:`Trigger` corresponding to an :class:`OwnerDecision`."""
    return _DECISION_TRIGGER[decision]
