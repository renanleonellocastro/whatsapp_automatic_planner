"""Unit tests for signed action tokens (AD-8)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from wapp_planner.domain.enums import OwnerDecision, OwnerInteractionKind
from wapp_planner.hitl.tokens import (
    ExpiredTokenError,
    InvalidTokenError,
    TokenSigner,
)
from wapp_planner.workflow.enums import Intent

T0 = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)


def test_issue_and_verify_round_trip() -> None:
    signer = TokenSigner("secret", ttl_seconds=3600)
    raw = signer.issue(
        request_id="r1",
        gate=OwnerInteractionKind.CLASSIFICATION,
        decision=OwnerDecision.CORRECT,
        now=T0,
        intent=Intent.QUOTE,
        revision_no=2,
    )
    token = signer.verify(raw, now=T0)
    assert token.request_id == "r1"
    assert token.gate is OwnerInteractionKind.CLASSIFICATION
    assert token.decision is OwnerDecision.CORRECT
    assert token.intent is Intent.QUOTE
    assert token.revision_no == 2
    assert token.expires_at == T0 + timedelta(seconds=3600)


def test_verify_just_before_expiry_ok_and_at_expiry_fails() -> None:
    signer = TokenSigner("secret", ttl_seconds=100)
    raw = signer.issue(
        request_id="r", gate=OwnerInteractionKind.APPROVAL, decision=OwnerDecision.APPROVE, now=T0
    )
    assert signer.verify(raw, now=T0 + timedelta(seconds=99)).request_id == "r"
    with pytest.raises(ExpiredTokenError):
        signer.verify(raw, now=T0 + timedelta(seconds=100))


@pytest.mark.parametrize("bad", ["no-dot", "too.many.dots", ""])
def test_verify_malformed_token(bad: str) -> None:
    signer = TokenSigner("secret")
    with pytest.raises(InvalidTokenError, match="malformed"):
        signer.verify(bad, now=T0)


def test_verify_rejects_tampered_payload() -> None:
    signer = TokenSigner("secret")
    raw = signer.issue(
        request_id="r", gate=OwnerInteractionKind.APPROVAL, decision=OwnerDecision.APPROVE, now=T0
    )
    payload, signature = raw.split(".")
    tampered = ("X" + payload[1:]) + "." + signature
    with pytest.raises(InvalidTokenError, match="signature"):
        signer.verify(tampered, now=T0)


def test_verify_rejects_wrong_secret() -> None:
    raw = TokenSigner("secret").issue(
        request_id="r", gate=OwnerInteractionKind.APPROVAL, decision=OwnerDecision.APPROVE, now=T0
    )
    with pytest.raises(InvalidTokenError):
        TokenSigner("other").verify(raw, now=T0)
