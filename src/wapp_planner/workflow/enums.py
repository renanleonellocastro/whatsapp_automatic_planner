"""Enumerations for the request lifecycle.

These are the stable vocabulary referenced across the system and in
``docs/REQUIREMENTS.md`` (§6 state machine, §7.4 classification).
"""

from __future__ import annotations

from enum import StrEnum


class RequestState(StrEnum):
    """Lifecycle state of a :class:`Request` (REQUIREMENTS §6)."""

    RECEIVED = "received"
    AGGREGATING = "aggregating"
    PROCESSING_MEDIA = "processing_media"
    CLASSIFYING = "classifying"
    AWAITING_CLASSIFICATION = "awaiting_classification"
    GENERATING = "generating"
    RENDERING = "rendering"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    DISCARDED = "discarded"
    FAILED = "failed"


class Intent(StrEnum):
    """Detected request intent (REQUIREMENTS FR-CLS-01)."""

    QUOTE = "quote"
    EXECUTION_PLAN = "execution_plan"
    NONE = "none"


class MessageType(StrEnum):
    """Inbound WhatsApp message types we accept (REQUIREMENTS FR-ING-04)."""

    TEXT = "text"
    AUDIO = "audio"
    VOICE = "voice"
    VIDEO = "video"
    IMAGE = "image"
    DOCUMENT = "document"


class Trigger(StrEnum):
    """Events that drive transitions in the state machine (REQUIREMENTS §6).

    Each trigger maps a current :class:`RequestState` to its successor in
    :data:`wapp_planner.workflow.state_machine.TRANSITIONS`.
    """

    START_AGGREGATION = "start_aggregation"
    WINDOW_CLOSED = "window_closed"
    MEDIA_PROCESSED = "media_processed"
    CLASSIFIED_ACTIONABLE = "classified_actionable"
    CLASSIFIED_NONE = "classified_none"
    OWNER_CONFIRMED = "owner_confirmed"
    OWNER_CORRECTED = "owner_corrected"
    OWNER_REJECTED = "owner_rejected"
    GENERATED = "generated"
    RENDERED = "rendered"
    OWNER_APPROVED = "owner_approved"
    OWNER_REQUESTED_REVISION = "owner_requested_revision"
    FAIL = "fail"
