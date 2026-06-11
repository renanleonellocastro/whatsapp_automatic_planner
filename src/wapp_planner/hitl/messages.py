"""Compose owner notification text and the signed action links (FR-NOT-02, AD-8).

Pure functions: given a signer + request they build the per-gate action links and
render the notification body. The notification language is English for now
(configurable later); generated client documents are English regardless (AD-5).
"""

from __future__ import annotations

from datetime import datetime

from wapp_planner.domain.enums import OwnerDecision, OwnerInteractionKind
from wapp_planner.domain.models import Request
from wapp_planner.hitl.tokens import TokenSigner
from wapp_planner.nlp.classifier import ClassificationResult
from wapp_planner.workflow.enums import Intent

ACTION_PATH = "/hitl/action"


def _link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}{ACTION_PATH}?token={token}"


def classification_links(
    base_url: str, signer: TokenSigner, request: Request, *, now: datetime
) -> dict[str, str]:
    """Build the HITL #1 action links (confirm / correct→intent / reject)."""

    def url(decision: OwnerDecision, intent: Intent | None = None) -> str:
        token = signer.issue(
            request_id=request.id,
            gate=OwnerInteractionKind.CLASSIFICATION,
            decision=decision,
            now=now,
            intent=intent,
        )
        return _link(base_url, token)

    return {
        "Confirm": url(OwnerDecision.CONFIRM),
        "It's a quote": url(OwnerDecision.CORRECT, Intent.QUOTE),
        "It's an execution plan": url(OwnerDecision.CORRECT, Intent.EXECUTION_PLAN),
        "Reject": url(OwnerDecision.REJECT),
    }


def approval_links(
    base_url: str, signer: TokenSigner, request: Request, *, now: datetime, revision_no: int
) -> dict[str, str]:
    """Build the HITL #2 action links (approve / request revision)."""

    def url(decision: OwnerDecision) -> str:
        token = signer.issue(
            request_id=request.id,
            gate=OwnerInteractionKind.APPROVAL,
            decision=decision,
            now=now,
            revision_no=revision_no,
        )
        return _link(base_url, token)

    return {"Approve": url(OwnerDecision.APPROVE), "Request revision": url(OwnerDecision.REVISE)}


def _render_links(links: dict[str, str]) -> str:
    return "\n".join(f"- {label}: {url}" for label, url in links.items())


def compose_classification_notification(
    request: Request,
    client_name: str,
    result: ClassificationResult,
    links: dict[str, str],
    *,
    low_confidence: bool,
) -> tuple[str, str]:
    """Return ``(subject, body)`` for the HITL #1 notification (FR-NOT-02/03)."""
    intent_label = result.intent.value
    subject = f"New {intent_label} request from {client_name}"
    flag_note = "  ⚠ low confidence" if low_confidence else ""
    body = (
        f"A new request was detected and classified as: {intent_label}.\n\n"
        f"Client: {client_name}\n"
        f"Request: {request.id}\n"
        f"Confidence: {result.confidence:.0%}{flag_note}\n"
        f"Why: {result.rationale}\n\n"
        f"Please confirm the classification:\n{_render_links(links)}"
    )
    return subject, body


def compose_delivery_notification(
    request: Request, revision_no: int, links: dict[str, str]
) -> tuple[str, str]:
    """Return ``(subject, body)`` for the HITL #2 document delivery (FR-DLV-05)."""
    subject = f"Document ready for review — request {request.id} (rev {revision_no})"
    body = (
        f"The {request.intent.value} document for request {request.id} "
        f"(revision {revision_no}) is attached.\n\n"
        f"Please review and choose:\n{_render_links(links)}\n\n"
        f"To request a revision, follow the revision link and include your feedback."
    )
    return subject, body
