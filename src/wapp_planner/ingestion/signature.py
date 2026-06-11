"""WhatsApp webhook verification & signature validation (FR-ING-02/03).

Two independent checks:

* :func:`verify_subscription` — the one-time GET handshake Meta performs when a
  webhook is registered (``hub.mode``/``hub.verify_token``/``hub.challenge``).
* :func:`is_valid_signature` — per-request HMAC-SHA256 validation of the raw
  body against the app secret (``X-Hub-Signature-256`` header).
"""

from __future__ import annotations

import hashlib
import hmac

_SIGNATURE_PREFIX = "sha256="


class WebhookVerificationError(Exception):
    """Raised when the subscription verification handshake fails."""


def verify_subscription(
    mode: str | None, token: str | None, challenge: str, *, expected_token: str
) -> str:
    """Return ``challenge`` if the subscription handshake is valid (FR-ING-02).

    Raises :class:`WebhookVerificationError` on a wrong mode or verify token.
    """
    if mode == "subscribe" and token is not None and hmac.compare_digest(token, expected_token):
        return challenge
    raise WebhookVerificationError("invalid webhook verification request")


def is_valid_signature(payload: bytes, signature_header: str | None, *, app_secret: str) -> bool:
    """Constant-time validate the ``X-Hub-Signature-256`` header (FR-ING-03)."""
    if not signature_header or not signature_header.startswith(_SIGNATURE_PREFIX):
        return False
    provided = signature_header[len(_SIGNATURE_PREFIX) :]
    expected = hmac.new(app_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)
