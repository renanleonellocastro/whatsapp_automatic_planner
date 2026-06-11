"""Unit tests for webhook verification & signature validation (FR-ING-02/03)."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from wapp_planner.ingestion.signature import (
    WebhookVerificationError,
    is_valid_signature,
    verify_subscription,
)

SECRET = "app-secret"


def _sign(payload: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def test_verify_subscription_ok() -> None:
    assert (
        verify_subscription("subscribe", "vt", "challenge-123", expected_token="vt")
        == "challenge-123"
    )


@pytest.mark.parametrize(
    ("mode", "token"),
    [("subscribe", "wrong"), ("unsubscribe", "vt"), (None, "vt"), ("subscribe", None)],
)
def test_verify_subscription_rejects(mode: str | None, token: str | None) -> None:
    with pytest.raises(WebhookVerificationError):
        verify_subscription(mode, token, "challenge", expected_token="vt")


def test_valid_signature_accepts_correct_hmac() -> None:
    payload = b'{"hello":"world"}'
    assert is_valid_signature(payload, _sign(payload), app_secret=SECRET)


def test_valid_signature_rejects_tampered_payload() -> None:
    payload = b'{"hello":"world"}'
    assert not is_valid_signature(b'{"hello":"evil"}', _sign(payload), app_secret=SECRET)


def test_valid_signature_rejects_wrong_secret() -> None:
    payload = b"x"
    assert not is_valid_signature(payload, _sign(payload, "other"), app_secret=SECRET)


@pytest.mark.parametrize("header", [None, "", "md5=abc", "deadbeef"])
def test_valid_signature_rejects_missing_or_malformed_header(header: str | None) -> None:
    assert not is_valid_signature(b"x", header, app_secret=SECRET)
