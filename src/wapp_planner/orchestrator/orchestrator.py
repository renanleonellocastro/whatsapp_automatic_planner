"""Application orchestrator — wires every stage over the state machine (§6).

Two entry points:

* :meth:`ingest` takes an aggregated batch of messages, processes media,
  classifies it, persists the request, and (if actionable) sends the HITL #1
  prompt — advancing RECEIVED → … → AWAITING_CLASSIFICATION / DISCARDED.
* :meth:`apply_owner_action` applies a resolved owner decision: confirm →
  generate+render+deliver; correct → re-notify; reject → discard; approve →
  complete; revise → regenerate with feedback (the FR-DLV-04 loop).

Every state change goes through the state machine, and the request is persisted
at each step so a restart resumes from the stored state (NFR-DURAB-01). Owner
actions are idempotent via the repository's interaction record (NFR-IDEMP-01).
"""

from __future__ import annotations

from datetime import datetime

from wapp_planner.aggregation.aggregator import AggregatedRequest
from wapp_planner.documents.branding import Branding
from wapp_planner.documents.generator import GeneratedDocument, GenerationError, Generator
from wapp_planner.documents.renderer import DOCX_MIME, PDF_MIME, render_document
from wapp_planner.domain.enums import OwnerDecision
from wapp_planner.domain.models import DocumentRevision, OwnerInteraction, Request
from wapp_planner.hitl.service import NotificationService, OwnerAction
from wapp_planner.media.processor import MediaProcessor
from wapp_planner.nlp.classifier import ClassificationResult, Classifier, is_low_confidence
from wapp_planner.persistence.repository import RequestRepository
from wapp_planner.providers.base import Attachment, DownloadedMedia, StorageProvider
from wapp_planner.workflow.enums import RequestState, Trigger
from wapp_planner.workflow.state_machine import next_state
from wapp_planner.workflow.triggers import trigger_for

LOW_CONFIDENCE_FLAG = "low_confidence"


class UnknownRequestError(Exception):
    """Raised when an owner action references a request that does not exist."""


class Orchestrator:
    """Coordinates ingestion and owner-action handling across all services."""

    def __init__(
        self,
        *,
        repository: RequestRepository,
        media_processor: MediaProcessor,
        classifier: Classifier,
        generator: Generator,
        notification_service: NotificationService,
        storage: StorageProvider,
        branding: Branding,
        confidence_threshold: float,
        notify_on_none: bool = False,
    ) -> None:
        self._repo = repository
        self._media = media_processor
        self._classifier = classifier
        self._generator = generator
        self._notify = notification_service
        self._storage = storage
        self._branding = branding
        self._threshold = confidence_threshold
        self._notify_on_none = notify_on_none

    # ── ingestion ────────────────────────────────────────────────────────
    def ingest(
        self,
        aggregated: AggregatedRequest,
        media: dict[str, DownloadedMedia],
        *,
        client_name: str,
        now: datetime,
        extra_flags: list[str] | None = None,
    ) -> Request:
        """Process, classify and (if actionable) notify on an aggregated batch."""
        request = Request(
            id=aggregated.request_id,
            client_id=aggregated.client_id,
            client_name=client_name,
            state=RequestState.RECEIVED,
            created_at=now,
            updated_at=now,
        )
        self._repo.save_request(request)
        self._repo.set_messages(request.id, aggregated.messages)

        request = self._transition(request, Trigger.START_AGGREGATION, now)
        request = self._transition(request, Trigger.WINDOW_CLOSED, now)

        transcript = self._media.build_transcript(aggregated.messages, media)
        request = request.model_copy(update={"normalized_transcript": transcript.render()})
        request = self._transition(request, Trigger.MEDIA_PROCESSED, now)

        result = self._classifier.classify(transcript.render())
        flags = list(extra_flags or [])
        if is_low_confidence(result, self._threshold):
            flags.append(LOW_CONFIDENCE_FLAG)
        request = request.model_copy(
            update={"intent": result.intent, "confidence": result.confidence, "flags": flags}
        )

        if not result.is_actionable:
            request = self._transition(request, Trigger.CLASSIFIED_NONE, now)
            if self._notify_on_none:
                self._notify.notify_classification(request, client_name, result, now=now)
            return request

        request = self._transition(request, Trigger.CLASSIFIED_ACTIONABLE, now)
        self._notify.notify_classification(request, client_name, result, now=now)
        return request

    # ── owner actions ────────────────────────────────────────────────────
    def apply_owner_action(self, action: OwnerAction, *, now: datetime) -> Request:
        """Apply a resolved owner decision to the referenced request."""
        request = self._repo.get_request(action.request_id)
        if request is None:
            raise UnknownRequestError(action.request_id)

        interaction = OwnerInteraction(
            id=action.action_id,
            request_id=action.request_id,
            kind=action.gate,
            decision=action.decision,
        )
        if not self._repo.record_interaction(interaction):
            return request  # duplicate click — idempotent no-op

        request = self._transition(request, trigger_for(action.decision), now)

        if action.decision is OwnerDecision.CONFIRM:
            return self._generate_render_deliver(request, now=now, feedback=None)
        if action.decision is OwnerDecision.CORRECT:
            request = request.model_copy(update={"intent": action.intent})
            self._repo.save_request(request)
            self._renotify_classification(request, now=now)
            return request
        if action.decision is OwnerDecision.REVISE:
            previous = self._repo.latest_revision(request.id)
            prior_content = previous.structured_content if previous else None
            return self._generate_render_deliver(
                request, now=now, feedback=action.feedback, previous_content=prior_content
            )
        # REJECT -> DISCARDED, APPROVE -> COMPLETED: transition is the whole effect.
        return request

    # ── helpers ──────────────────────────────────────────────────────────
    def _transition(self, request: Request, trigger: Trigger, now: datetime) -> Request:
        updated = request.model_copy(
            update={"state": next_state(request.state, trigger), "updated_at": now}
        )
        self._repo.save_request(updated)
        return updated

    def _renotify_classification(self, request: Request, *, now: datetime) -> None:
        result = ClassificationResult(
            intent=request.intent, confidence=1.0, rationale="Corrected by owner."
        )
        self._notify.notify_classification(
            request, request.client_name or request.client_id, result, now=now
        )

    def _generate_render_deliver(
        self,
        request: Request,
        *,
        now: datetime,
        feedback: str | None,
        previous_content: dict[str, object] | None = None,
    ) -> Request:
        revision_no = request.current_revision + 1
        try:
            doc = self._generator.generate(
                request.intent,
                request.normalized_transcript or "",
                client_name=request.client_name or request.client_id,
                revision_no=revision_no,
                feedback=feedback,
                previous_content=previous_content,
            )
        except GenerationError:
            self._transition(request, Trigger.FAIL, now)
            raise

        attachments = render_document(
            doc.content,
            self._branding,
            basename=f"{request.intent.value}-{request.id}-r{revision_no}",
        )
        pdf_ref, docx_ref = self._store_artifacts(request.id, revision_no, attachments)
        self._repo.add_revision(
            DocumentRevision(
                id=f"{request.id}-rev-{revision_no}",
                request_id=request.id,
                revision_no=revision_no,
                structured_content=doc.structured_content,
                feedback=feedback,
                pdf_ref=pdf_ref,
                docx_ref=docx_ref,
                llm_meta=_llm_meta(doc),
                created_at=now,
            )
        )
        request = request.model_copy(update={"current_revision": revision_no})
        request = self._transition(request, Trigger.GENERATED, now)
        request = self._transition(request, Trigger.RENDERED, now)
        self._notify.deliver_document(request, revision_no, attachments, now=now)
        return request

    def _store_artifacts(
        self, request_id: str, revision_no: int, attachments: list[Attachment]
    ) -> tuple[str | None, str | None]:
        refs: dict[str, str] = {}
        for att in attachments:
            key = f"{request_id}/r{revision_no}/{att.filename}"
            refs[att.content_type] = self._storage.put(
                key, att.content, content_type=att.content_type
            )
        return refs.get(PDF_MIME), refs.get(DOCX_MIME)


def _llm_meta(doc: GeneratedDocument) -> dict[str, object]:
    return {
        "model": doc.model,
        "input_tokens": doc.input_tokens,
        "output_tokens": doc.output_tokens,
        "cost_usd": doc.cost_usd,
        "attempts": doc.attempts,
    }
