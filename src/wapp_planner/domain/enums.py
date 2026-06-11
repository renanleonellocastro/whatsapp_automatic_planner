"""Domain-level enumerations (distinct from the workflow lifecycle enums)."""

from __future__ import annotations

from enum import StrEnum


class Channel(StrEnum):
    """A communication channel for owner notifications/deliveries (AD-3)."""

    EMAIL = "email"
    WHATSAPP = "whatsapp"
    BOTH = "both"

    def includes(self, other: Channel) -> bool:
        """Whether sending on ``self`` reaches the single channel ``other``.

        ``BOTH`` reaches every concrete channel; a concrete channel reaches only
        itself. Used by the notifier to fan a message out per configured channel.
        """
        return self is Channel.BOTH or self is other


class ProcessingStatus(StrEnum):
    """Per-message media-processing outcome (FR-MED-07)."""

    PENDING = "pending"
    PROCESSED = "processed"
    UNPROCESSABLE = "unprocessable"


class OwnerInteractionKind(StrEnum):
    """Which human-in-the-loop gate an owner response belongs to."""

    CLASSIFICATION = "classification"
    APPROVAL = "approval"


class OwnerDecision(StrEnum):
    """The decision an owner conveyed at a HITL gate (FR-CNF-02, FR-DLV-02)."""

    CONFIRM = "confirm"
    CORRECT = "correct"
    REJECT = "reject"
    APPROVE = "approve"
    REVISE = "revise"
