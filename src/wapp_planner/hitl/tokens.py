"""Signed, expiring action tokens for HITL links (AD-8).

A token authorizes one owner action on one request at one gate. It is encoded as
``<base64url(payload)>.<hmac-sha256>`` so a click can be verified without server
state: the signature proves authenticity and the embedded ``expires_at`` bounds
its lifetime. Free-text revision feedback is supplied alongside the token at
click time (it is not signed — the token already authorizes the action).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timedelta

from pydantic import BaseModel

from wapp_planner.domain.enums import OwnerDecision, OwnerInteractionKind
from wapp_planner.workflow.enums import Intent


class TokenError(Exception):
    """Base class for token validation failures."""


class InvalidTokenError(TokenError):
    """Raised when a token is malformed or its signature does not verify."""


class ExpiredTokenError(TokenError):
    """Raised when a token's ``expires_at`` is in the past."""


class ActionToken(BaseModel):
    """The signed authorization payload for one HITL action."""

    request_id: str
    gate: OwnerInteractionKind
    decision: OwnerDecision
    expires_at: datetime
    intent: Intent | None = None
    revision_no: int = 0


class TokenSigner:
    """Issues and verifies :class:`ActionToken` strings with an HMAC secret."""

    def __init__(self, secret: str, *, ttl_seconds: int = 7 * 24 * 3600) -> None:
        self._secret = secret.encode("utf-8")
        self._ttl = timedelta(seconds=ttl_seconds)

    def _sign(self, payload_b64: str) -> str:
        return hmac.new(self._secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()

    def issue(
        self,
        *,
        request_id: str,
        gate: OwnerInteractionKind,
        decision: OwnerDecision,
        now: datetime,
        intent: Intent | None = None,
        revision_no: int = 0,
    ) -> str:
        """Create a signed token string for an action, expiring ``ttl`` from now."""
        token = ActionToken(
            request_id=request_id,
            gate=gate,
            decision=decision,
            expires_at=now + self._ttl,
            intent=intent,
            revision_no=revision_no,
        )
        payload = base64.urlsafe_b64encode(token.model_dump_json().encode("utf-8"))
        payload_b64 = payload.rstrip(b"=").decode("ascii")
        return f"{payload_b64}.{self._sign(payload_b64)}"

    def verify(self, raw: str, *, now: datetime) -> ActionToken:
        """Verify signature + expiry and return the decoded token."""
        parts = raw.split(".")
        if len(parts) != 2:
            raise InvalidTokenError("malformed token")
        payload_b64, signature = parts
        if not hmac.compare_digest(self._sign(payload_b64), signature):
            raise InvalidTokenError("signature mismatch")
        # Signature verified -> payload is authentic and decodes cleanly.
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        token = ActionToken.model_validate_json(base64.urlsafe_b64decode(padded))
        if now >= token.expires_at:
            raise ExpiredTokenError("token expired")
        return token
