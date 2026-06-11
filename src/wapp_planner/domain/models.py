"""Domain entities (REQUIREMENTS §9).

Pydantic models — persistence-agnostic, validated, and serializable. They carry
no I/O; the orchestrator and repositories move them through the state machine.
Timestamps default via :mod:`wapp_planner.clock` so tests stay deterministic by
injecting explicit values.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from wapp_planner import clock
from wapp_planner.domain.enums import (
    Channel,
    OwnerDecision,
    OwnerInteractionKind,
    ProcessingStatus,
)
from wapp_planner.workflow.enums import Intent, MessageType, RequestState


class Client(BaseModel):
    """A customer who sends jobs over WhatsApp (FR-CFG-01)."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    phone_numbers: frozenset[str] = Field(default_factory=frozenset)
    metadata: dict[str, str] = Field(default_factory=dict)
    branding_profile: str | None = None

    @field_validator("phone_numbers", mode="before")
    @classmethod
    def _coerce_numbers(cls, value: object) -> object:
        """Accept any iterable of numbers and normalize to a frozenset."""
        if isinstance(value, str):
            return frozenset({value})
        if isinstance(value, frozenset):
            return value
        if isinstance(value, (list, tuple, set)):
            return frozenset(value)
        return value

    def owns_number(self, phone_number: str) -> bool:
        return phone_number in self.phone_numbers


class Message(BaseModel):
    """A single inbound WhatsApp message within a request (§9)."""

    id: str
    type: MessageType
    order: int
    received_at: datetime = Field(default_factory=clock.now)
    text: str | None = None
    caption: str | None = None
    media_id: str | None = None
    mime_type: str | None = None
    filename: str | None = None
    raw_ref: str | None = None
    transcript: str | None = None
    processing_status: ProcessingStatus = ProcessingStatus.PENDING

    @property
    def is_media(self) -> bool:
        """True for message types whose payload must be downloaded/processed."""
        return self.type is not MessageType.TEXT

    def resolved_text(self) -> str | None:
        """The best available text for this message: transcript else literal text."""
        return self.transcript if self.transcript is not None else self.text


class DocumentRevision(BaseModel):
    """One rendered revision of a generated document (§9, FR-REV-01)."""

    id: str
    request_id: str
    revision_no: int = Field(ge=0)
    structured_content: dict[str, object] = Field(default_factory=dict)
    feedback: str | None = None
    pdf_ref: str | None = None
    docx_ref: str | None = None
    llm_meta: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=clock.now)


class OwnerInteraction(BaseModel):
    """A recorded owner response at a HITL gate (§9; supports idempotency/audit)."""

    id: str
    request_id: str
    kind: OwnerInteractionKind
    decision: OwnerDecision
    channel: Channel | None = None
    raw_response: str | None = None
    received_at: datetime = Field(default_factory=clock.now)


class Request(BaseModel):
    """A unit of work: one client's batched messages asking for one document (§9)."""

    id: str
    client_id: str
    client_name: str | None = None
    state: RequestState = RequestState.RECEIVED
    intent: Intent = Intent.NONE
    confidence: float | None = None
    created_at: datetime = Field(default_factory=clock.now)
    updated_at: datetime = Field(default_factory=clock.now)
    normalized_transcript: str | None = None
    current_revision: int = Field(default=0, ge=0)
    flags: list[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def _confidence_in_range(cls, value: float | None) -> float | None:
        if value is not None and not (0.0 <= value <= 1.0):
            raise ValueError("confidence must be within [0, 1]")
        return value

    def has_flag(self, flag: str) -> bool:
        return flag in self.flags

    def with_flag(self, flag: str) -> Request:
        """Return a copy with ``flag`` added (idempotent)."""
        if flag in self.flags:
            return self
        return self.model_copy(update={"flags": [*self.flags, flag]})
