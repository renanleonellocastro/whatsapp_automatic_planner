"""Notification & owner-response service (FR-NOT-*, FR-CNF-03, FR-DLV-01/02).

Sends the two HITL prompts (classification confirmation; document delivery) over
the configured channel(s) and resolves a clicked action link back into a
validated :class:`OwnerAction` for the orchestrator to apply.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from pydantic import BaseModel

from wapp_planner.domain.enums import Channel, OwnerDecision, OwnerInteractionKind
from wapp_planner.domain.models import Request
from wapp_planner.hitl.dispatcher import ChannelDispatcher
from wapp_planner.hitl.messages import (
    approval_links,
    classification_links,
    compose_classification_notification,
    compose_delivery_notification,
)
from wapp_planner.hitl.tokens import TokenSigner
from wapp_planner.nlp.classifier import ClassificationResult, is_low_confidence
from wapp_planner.providers.base import Attachment
from wapp_planner.workflow.enums import Intent


def _action_id(token_str: str) -> str:
    """Stable idempotency id for a clicked link (same token -> same id)."""
    return hashlib.sha256(token_str.encode("utf-8")).hexdigest()


class OwnerAction(BaseModel):
    """A validated owner decision resolved from a clicked action link."""

    request_id: str
    gate: OwnerInteractionKind
    decision: OwnerDecision
    action_id: str
    intent: Intent | None = None
    revision_no: int = 0
    feedback: str | None = None


class NotificationService:
    """Composes and dispatches HITL prompts; resolves owner responses."""

    def __init__(
        self,
        *,
        signer: TokenSigner,
        dispatcher: ChannelDispatcher,
        base_url: str,
        confidence_threshold: float,
        notify_channel: Channel,
        deliver_channel: Channel,
    ) -> None:
        self._signer = signer
        self._dispatcher = dispatcher
        self._base_url = base_url
        self._confidence_threshold = confidence_threshold
        self._notify_channel = notify_channel
        self._deliver_channel = deliver_channel

    def notify_classification(
        self, request: Request, client_name: str, result: ClassificationResult, *, now: datetime
    ) -> dict[Channel, str]:
        """Send the HITL #1 classification-confirmation prompt (FR-NOT-01/02/03)."""
        low_conf = is_low_confidence(result, self._confidence_threshold)
        links = classification_links(self._base_url, self._signer, request, now=now)
        subject, body = compose_classification_notification(
            request, client_name, result, links, low_confidence=low_conf
        )
        return self._dispatcher.send(self._notify_channel, subject=subject, body=body)

    def deliver_document(
        self,
        request: Request,
        revision_no: int,
        attachments: list[Attachment],
        *,
        now: datetime,
    ) -> dict[Channel, str]:
        """Send the HITL #2 document-delivery prompt with attachments (FR-DLV-01/05)."""
        links = approval_links(
            self._base_url, self._signer, request, now=now, revision_no=revision_no
        )
        subject, body = compose_delivery_notification(request, revision_no, links)
        return self._dispatcher.send(
            self._deliver_channel, subject=subject, body=body, attachments=attachments
        )

    def resolve_action(
        self, token_str: str, *, now: datetime, feedback: str | None = None
    ) -> OwnerAction:
        """Verify a clicked link's token and return the owner's decision (FR-CNF-03)."""
        token = self._signer.verify(token_str, now=now)
        return OwnerAction(
            request_id=token.request_id,
            gate=token.gate,
            decision=token.decision,
            action_id=_action_id(token_str),
            intent=token.intent,
            revision_no=token.revision_no,
            feedback=feedback,
        )
