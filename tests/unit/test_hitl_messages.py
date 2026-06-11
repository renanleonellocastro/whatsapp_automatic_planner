"""Unit tests for HITL message/link composition (FR-NOT-02, AD-8)."""

from __future__ import annotations

from datetime import UTC, datetime

from wapp_planner.domain.models import Request
from wapp_planner.hitl.messages import (
    approval_links,
    classification_links,
    compose_classification_notification,
    compose_delivery_notification,
)
from wapp_planner.hitl.tokens import TokenSigner
from wapp_planner.nlp.classifier import ClassificationResult
from wapp_planner.workflow.enums import Intent

T0 = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)
BASE = "https://hooks.example.com/"


def _request() -> Request:
    return Request(id="req-1", client_id="c1", intent=Intent.QUOTE)


def test_classification_links_are_signed_and_verifiable() -> None:
    signer = TokenSigner("secret")
    links = classification_links(BASE, signer, _request(), now=T0)
    assert set(links) == {"Confirm", "It's a quote", "It's an execution plan", "Reject"}
    for url in links.values():
        assert url.startswith("https://hooks.example.com/hitl/action?token=")
    # the "It's an execution plan" link decodes to a CORRECT->execution_plan token
    token_str = links["It's an execution plan"].split("token=")[1]
    token = signer.verify(token_str, now=T0)
    assert token.intent is Intent.EXECUTION_PLAN


def test_approval_links() -> None:
    signer = TokenSigner("secret")
    links = approval_links(BASE, signer, _request(), now=T0, revision_no=3)
    assert set(links) == {"Approve", "Request revision"}
    token = signer.verify(links["Request revision"].split("token=")[1], now=T0)
    assert token.revision_no == 3


def test_compose_classification_notification_high_confidence() -> None:
    result = ClassificationResult(intent=Intent.QUOTE, confidence=0.9, rationale="asks price")
    subject, body = compose_classification_notification(
        _request(), "Bob Builder", result, {"Confirm": "https://x/1"}, low_confidence=False
    )
    assert subject == "New quote request from Bob Builder"
    assert "Client: Bob Builder" in body
    assert "Confidence: 90%" in body
    assert "asks price" in body
    assert "Confirm: https://x/1" in body
    assert "low confidence" not in body


def test_compose_classification_notification_low_confidence_flag() -> None:
    result = ClassificationResult(intent=Intent.QUOTE, confidence=0.3, rationale="unsure")
    _, body = compose_classification_notification(
        _request(), "Bob", result, {}, low_confidence=True
    )
    assert "low confidence" in body


def test_compose_delivery_notification() -> None:
    subject, body = compose_delivery_notification(_request(), 2, {"Approve": "https://x/a"})
    assert "rev 2" in subject
    assert "revision 2" in body
    assert "Approve: https://x/a" in body
