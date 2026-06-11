"""Unit tests for domain models (§9)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from wapp_planner.domain.enums import ProcessingStatus
from wapp_planner.domain.models import (
    Client,
    DocumentRevision,
    Message,
    Request,
)
from wapp_planner.workflow.enums import Intent, MessageType, RequestState

FIXED = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)


# ── Client ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+15551234567", {"+15551234567"}),
        (["+1", "+2"], {"+1", "+2"}),
        (("+1", "+1"), {"+1"}),
        ({"+3"}, {"+3"}),
        (frozenset({"+9"}), {"+9"}),
    ],
)
def test_client_coerces_phone_numbers(raw: object, expected: set[str]) -> None:
    client = Client(id="c1", name="Acme", phone_numbers=raw)
    assert set(client.phone_numbers) == expected


def test_client_invalid_phone_numbers_type_raises() -> None:
    with pytest.raises(ValidationError):
        Client(id="c1", name="Acme", phone_numbers=123)


def test_client_owns_number() -> None:
    client = Client(id="c1", name="Acme", phone_numbers=["+1", "+2"])
    assert client.owns_number("+1")
    assert not client.owns_number("+9")


def test_client_is_frozen() -> None:
    client = Client(id="c1", name="Acme")
    with pytest.raises(ValidationError):
        client.name = "Other"  # type: ignore[misc]


# ── Message ─────────────────────────────────────────────────────────────
def test_message_is_media() -> None:
    text = Message(id="m1", type=MessageType.TEXT, order=0)
    audio = Message(id="m2", type=MessageType.AUDIO, order=1)
    assert not text.is_media
    assert audio.is_media


def test_message_resolved_text_prefers_transcript() -> None:
    m = Message(id="m1", type=MessageType.AUDIO, order=0, text="caption", transcript="spoken")
    assert m.resolved_text() == "spoken"


def test_message_resolved_text_falls_back_to_text() -> None:
    m = Message(id="m1", type=MessageType.TEXT, order=0, text="hi")
    assert m.resolved_text() == "hi"


def test_message_defaults() -> None:
    m = Message(id="m1", type=MessageType.TEXT, order=0)
    assert m.processing_status is ProcessingStatus.PENDING
    assert m.received_at.tzinfo is not None  # default_factory clock.now


# ── DocumentRevision ────────────────────────────────────────────────────
def test_document_revision_negative_revision_rejected() -> None:
    with pytest.raises(ValidationError):
        DocumentRevision(id="d1", request_id="r1", revision_no=-1)


def test_document_revision_minimal() -> None:
    d = DocumentRevision(id="d1", request_id="r1", revision_no=0)
    assert d.structured_content == {}
    assert d.created_at.tzinfo is not None


# ── Request ─────────────────────────────────────────────────────────────
def test_request_defaults() -> None:
    r = Request(id="r1", client_id="c1")
    assert r.state is RequestState.RECEIVED
    assert r.intent is Intent.NONE
    assert r.current_revision == 0
    assert r.flags == []


@pytest.mark.parametrize("value", [0.0, 0.5, 1.0, None])
def test_request_confidence_accepts_valid(value: float | None) -> None:
    r = Request(id="r1", client_id="c1", confidence=value)
    assert r.confidence == value


@pytest.mark.parametrize("value", [-0.01, 1.01, 2.0])
def test_request_confidence_rejects_out_of_range(value: float) -> None:
    with pytest.raises(ValidationError):
        Request(id="r1", client_id="c1", confidence=value)


def test_request_flags() -> None:
    r = Request(id="r1", client_id="c1")
    assert not r.has_flag("low_confidence")
    flagged = r.with_flag("low_confidence")
    assert flagged.has_flag("low_confidence")
    # idempotent: adding again returns the same instance
    assert flagged.with_flag("low_confidence") is flagged
    # original unchanged (immutable update)
    assert not r.has_flag("low_confidence")


def test_request_negative_revision_rejected() -> None:
    with pytest.raises(ValidationError):
        Request(id="r1", client_id="c1", current_revision=-1)
