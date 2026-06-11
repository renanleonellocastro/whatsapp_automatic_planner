"""Unit tests for the notification & response service (FR-NOT-*, FR-CNF-03)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from wapp_planner.domain.enums import Channel, OwnerDecision, OwnerInteractionKind
from wapp_planner.domain.models import Request
from wapp_planner.hitl.dispatcher import ChannelDispatcher, ChannelTarget
from wapp_planner.hitl.service import NotificationService
from wapp_planner.hitl.tokens import ExpiredTokenError, TokenSigner
from wapp_planner.nlp.classifier import ClassificationResult
from wapp_planner.providers.base import Attachment
from wapp_planner.providers.fakes import RecordingNotifier
from wapp_planner.workflow.enums import Intent

T0 = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)


def _service(
    *, notify: Channel = Channel.EMAIL, deliver: Channel = Channel.WHATSAPP
) -> tuple[NotificationService, dict[Channel, RecordingNotifier], TokenSigner]:
    notifiers = {c: RecordingNotifier(c) for c in (Channel.EMAIL, Channel.WHATSAPP)}
    dispatcher = ChannelDispatcher(
        {c: ChannelTarget(notifier=n, recipient=f"to-{c.value}") for c, n in notifiers.items()}
    )
    signer = TokenSigner("secret", ttl_seconds=3600)
    service = NotificationService(
        signer=signer,
        dispatcher=dispatcher,
        base_url="https://h",
        confidence_threshold=0.6,
        notify_channel=notify,
        deliver_channel=deliver,
    )
    return service, notifiers, signer


def _request() -> Request:
    return Request(id="req-1", client_id="c1", intent=Intent.QUOTE)


def test_notify_classification_sends_on_notify_channel() -> None:
    service, notifiers, _ = _service(notify=Channel.EMAIL)
    result = ClassificationResult(intent=Intent.QUOTE, confidence=0.9, rationale="price")
    sent = service.notify_classification(_request(), "Bob", result, now=T0)
    assert set(sent) == {Channel.EMAIL}
    body = notifiers[Channel.EMAIL].sent[0].body
    assert "Confirm:" in body
    assert "low confidence" not in body


def test_notify_classification_flags_low_confidence() -> None:
    service, notifiers, _ = _service()
    result = ClassificationResult(intent=Intent.QUOTE, confidence=0.3, rationale="unsure")
    service.notify_classification(_request(), "Bob", result, now=T0)
    assert "low confidence" in notifiers[Channel.EMAIL].sent[0].body


def test_deliver_document_sends_with_attachments() -> None:
    service, notifiers, _ = _service(deliver=Channel.WHATSAPP)
    att = Attachment(filename="q.pdf", content=b"%PDF", content_type="application/pdf")
    sent = service.deliver_document(_request(), 1, [att], now=T0)
    assert set(sent) == {Channel.WHATSAPP}
    delivered = notifiers[Channel.WHATSAPP].sent[0]
    assert delivered.attachments == [att]
    assert "Approve:" in delivered.body


def test_resolve_action_returns_validated_decision() -> None:
    service, _, signer = _service()
    raw = signer.issue(
        request_id="req-1",
        gate=OwnerInteractionKind.APPROVAL,
        decision=OwnerDecision.REVISE,
        now=T0,
        revision_no=2,
    )
    action = service.resolve_action(raw, now=T0, feedback="add more detail")
    assert action.request_id == "req-1"
    assert action.gate is OwnerInteractionKind.APPROVAL
    assert action.decision is OwnerDecision.REVISE
    assert action.revision_no == 2
    assert action.feedback == "add more detail"


def test_resolve_action_propagates_token_errors() -> None:
    service, _, signer = _service()
    raw = signer.issue(
        request_id="r", gate=OwnerInteractionKind.APPROVAL, decision=OwnerDecision.APPROVE, now=T0
    )
    from datetime import timedelta

    with pytest.raises(ExpiredTokenError):
        service.resolve_action(raw, now=T0 + timedelta(seconds=3600))
