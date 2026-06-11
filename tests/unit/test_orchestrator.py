"""Unit tests for the orchestrator (§6, FR-DLV-04, NFR-IDEMP-01)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from wapp_planner.aggregation.aggregator import AggregatedRequest
from wapp_planner.documents.branding import Branding
from wapp_planner.documents.generator import GenerationError, Generator
from wapp_planner.domain.enums import Channel, OwnerDecision, OwnerInteractionKind
from wapp_planner.domain.models import Message, Request
from wapp_planner.hitl.dispatcher import ChannelDispatcher, ChannelTarget
from wapp_planner.hitl.service import NotificationService, OwnerAction
from wapp_planner.hitl.tokens import TokenSigner
from wapp_planner.media.extractors import FakeDocumentTextExtractor, FakeVideoProcessor
from wapp_planner.media.processor import MediaProcessor
from wapp_planner.nlp.classifier import Classifier
from wapp_planner.orchestrator.orchestrator import Orchestrator, UnknownRequestError
from wapp_planner.persistence.repository import InMemoryRequestRepository
from wapp_planner.providers.fakes import (
    FakeLLMProvider,
    FakeTranscriptionProvider,
    FakeVisionProvider,
    InMemoryStorage,
    RecordingNotifier,
)
from wapp_planner.workflow.enums import Intent, MessageType, RequestState
from wapp_planner.workflow.state_machine import IllegalTransitionError

T0 = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)

QUOTE_CLS = '{"intent": "quote", "confidence": 0.9, "rationale": "asks price"}'
NONE_CLS = '{"intent": "none", "confidence": 0.95, "rationale": "greeting"}'
LOW_CLS = '{"intent": "quote", "confidence": 0.3, "rationale": "unsure"}'

QUOTE_DOC = json.dumps(
    {
        "title": "Estimate",
        "prepared_for": "Customer",
        "scope_summary": "scope",
        "line_items": [
            {"description": "Demo", "quantity": 1, "unit": "job", "unit_price": 500, "total": 500}
        ],
        "subtotal": 500,
        "total": 500,
    }
)


class _Harness:
    def __init__(self, classification: str, generation: str, *, notify_on_none: bool) -> None:
        self.repo = InMemoryRequestRepository()
        self.storage = InMemoryStorage()
        self.notifiers = {c: RecordingNotifier(c) for c in (Channel.EMAIL, Channel.WHATSAPP)}
        dispatcher = ChannelDispatcher(
            {
                c: ChannelTarget(notifier=n, recipient=f"to-{c.value}")
                for c, n in self.notifiers.items()
            }
        )
        self.signer = TokenSigner("secret")
        self.notify = NotificationService(
            signer=self.signer,
            dispatcher=dispatcher,
            base_url="https://h",
            confidence_threshold=0.6,
            notify_channel=Channel.EMAIL,
            deliver_channel=Channel.WHATSAPP,
        )
        media = MediaProcessor(
            transcriber=FakeTranscriptionProvider(default_text="spoken"),
            vision=FakeVisionProvider(default="img"),
            video=FakeVideoProcessor(),
            documents=FakeDocumentTextExtractor(),
            transcription_model="w",
            vision_model="v",
        )
        self.orch = Orchestrator(
            repository=self.repo,
            media_processor=media,
            classifier=Classifier(
                FakeLLMProvider(default_text=classification), model="m", prompt_version="v1"
            ),
            generator=Generator(
                FakeLLMProvider(default_text=generation),
                model="m",
                prompt_version="v1",
                sleep=lambda _: None,
            ),
            notification_service=self.notify,
            storage=self.storage,
            branding=Branding(),
            confidence_threshold=0.6,
            notify_on_none=notify_on_none,
        )


def _harness(
    classification: str = QUOTE_CLS, generation: str = QUOTE_DOC, *, notify_on_none: bool = False
) -> _Harness:
    return _Harness(classification, generation, notify_on_none=notify_on_none)


def _aggregated(text: str = "need a quote") -> AggregatedRequest:
    return AggregatedRequest(
        request_id="req-1",
        client_id="c1",
        started_at=T0,
        last_at=T0,
        messages=[Message(id="m1", type=MessageType.TEXT, order=0, text=text)],
    )


def _ingest_quote(h: _Harness) -> Request:
    return h.orch.ingest(_aggregated(), {}, client_name="Bob", now=T0)


def _action(decision: OwnerDecision, gate: OwnerInteractionKind, **kw: object) -> OwnerAction:
    return OwnerAction(
        request_id="req-1",
        gate=gate,
        decision=decision,
        action_id=f"{decision.value}-1",
        **kw,  # type: ignore[arg-type]
    )


# ── ingestion ────────────────────────────────────────────────────────────
def test_ingest_actionable_quote_notifies_owner() -> None:
    h = _harness()
    request = _ingest_quote(h)
    assert request.state is RequestState.AWAITING_CLASSIFICATION
    assert request.intent is Intent.QUOTE
    assert request.confidence == 0.9
    assert request.flags == []
    assert request.normalized_transcript is not None
    assert len(h.notifiers[Channel.EMAIL].sent) == 1  # HITL #1 sent on notify channel


def test_ingest_low_confidence_flagged() -> None:
    h = _harness(classification=LOW_CLS)
    request = _ingest_quote(h)
    assert request.flags == ["low_confidence"]
    assert request.state is RequestState.AWAITING_CLASSIFICATION


def test_ingest_none_discards_without_notifying() -> None:
    h = _harness(classification=NONE_CLS)
    request = _ingest_quote(h)
    assert request.state is RequestState.DISCARDED
    assert h.notifiers[Channel.EMAIL].sent == []


def test_ingest_none_notifies_when_configured() -> None:
    h = _harness(classification=NONE_CLS, notify_on_none=True)
    request = _ingest_quote(h)
    assert request.state is RequestState.DISCARDED
    assert len(h.notifiers[Channel.EMAIL].sent) == 1


# ── confirm → generate/render/deliver ─────────────────────────────────────
def test_confirm_generates_renders_and_delivers() -> None:
    h = _harness()
    _ingest_quote(h)
    request = h.orch.apply_owner_action(
        _action(OwnerDecision.CONFIRM, OwnerInteractionKind.CLASSIFICATION), now=T0
    )
    assert request.state is RequestState.AWAITING_APPROVAL
    assert request.current_revision == 1
    # a revision was persisted with both artifact refs
    rev = h.repo.latest_revision("req-1")
    assert rev.revision_no == 1
    assert rev.pdf_ref is not None and rev.docx_ref is not None
    assert rev.llm_meta["model"] == "m"
    # artifacts stored
    assert h.storage.exists("req-1/r1/quote-req-1-r1.pdf")
    assert h.storage.exists("req-1/r1/quote-req-1-r1.docx")
    # delivered on the deliver channel with attachments
    delivered = h.notifiers[Channel.WHATSAPP].sent[-1]
    assert len(delivered.attachments) == 2


# ── correct / reject ───────────────────────────────────────────────────────
def test_correct_updates_intent_and_renotifies() -> None:
    h = _harness()
    _ingest_quote(h)
    request = h.orch.apply_owner_action(
        _action(
            OwnerDecision.CORRECT,
            OwnerInteractionKind.CLASSIFICATION,
            intent=Intent.EXECUTION_PLAN,
        ),
        now=T0,
    )
    assert request.state is RequestState.AWAITING_CLASSIFICATION  # self-loop
    assert request.intent is Intent.EXECUTION_PLAN
    assert len(h.notifiers[Channel.EMAIL].sent) == 2  # original + re-notify


def test_reject_discards() -> None:
    h = _harness()
    _ingest_quote(h)
    request = h.orch.apply_owner_action(
        _action(OwnerDecision.REJECT, OwnerInteractionKind.CLASSIFICATION), now=T0
    )
    assert request.state is RequestState.DISCARDED


# ── approve / revise loop ──────────────────────────────────────────────────
def _confirm(h: _Harness) -> Request:
    _ingest_quote(h)
    return h.orch.apply_owner_action(
        _action(OwnerDecision.CONFIRM, OwnerInteractionKind.CLASSIFICATION), now=T0
    )


def test_approve_completes() -> None:
    h = _harness()
    _confirm(h)
    request = h.orch.apply_owner_action(
        _action(OwnerDecision.APPROVE, OwnerInteractionKind.APPROVAL, revision_no=1), now=T0
    )
    assert request.state is RequestState.COMPLETED


def test_revise_regenerates_new_revision() -> None:
    h = _harness()
    _confirm(h)
    request = h.orch.apply_owner_action(
        OwnerAction(
            request_id="req-1",
            gate=OwnerInteractionKind.APPROVAL,
            decision=OwnerDecision.REVISE,
            action_id="revise-1",
            revision_no=1,
            feedback="make the demo cheaper",
        ),
        now=T0,
    )
    assert request.state is RequestState.AWAITING_APPROVAL
    assert request.current_revision == 2
    revisions = h.repo.get_revisions("req-1")
    assert [r.revision_no for r in revisions] == [1, 2]
    assert revisions[1].feedback == "make the demo cheaper"


def test_revise_without_prior_revision_uses_no_previous_content() -> None:
    # Construct a request already awaiting approval but with no stored revision.
    h = _harness()
    h.repo.save_request(
        Request(
            id="req-1",
            client_id="c1",
            client_name="Bob",
            intent=Intent.QUOTE,
            state=RequestState.AWAITING_APPROVAL,
            current_revision=1,
            normalized_transcript="t",
        )
    )
    request = h.orch.apply_owner_action(
        OwnerAction(
            request_id="req-1",
            gate=OwnerInteractionKind.APPROVAL,
            decision=OwnerDecision.REVISE,
            action_id="revise-x",
            revision_no=1,
            feedback="tweak",
        ),
        now=T0,
    )
    assert request.state is RequestState.AWAITING_APPROVAL
    assert request.current_revision == 2


# ── idempotency / errors ───────────────────────────────────────────────────
def test_duplicate_action_is_idempotent() -> None:
    h = _harness()
    _ingest_quote(h)
    action = _action(OwnerDecision.CONFIRM, OwnerInteractionKind.CLASSIFICATION)
    first = h.orch.apply_owner_action(action, now=T0)
    second = h.orch.apply_owner_action(action, now=T0)  # same action_id
    assert first.state is second.state is RequestState.AWAITING_APPROVAL
    assert len(h.repo.get_revisions("req-1")) == 1  # not regenerated
    assert len(h.notifiers[Channel.WHATSAPP].sent) == 1  # delivered once


def test_unknown_request_raises() -> None:
    h = _harness()
    with pytest.raises(UnknownRequestError):
        h.orch.apply_owner_action(
            _action(OwnerDecision.CONFIRM, OwnerInteractionKind.CLASSIFICATION), now=T0
        )


def test_illegal_action_for_state_raises() -> None:
    h = _harness()
    _ingest_quote(h)  # AWAITING_CLASSIFICATION
    with pytest.raises(IllegalTransitionError):
        h.orch.apply_owner_action(
            _action(OwnerDecision.APPROVE, OwnerInteractionKind.APPROVAL, revision_no=1), now=T0
        )


def test_generation_failure_marks_request_failed() -> None:
    h = _harness(generation="not valid json")
    _ingest_quote(h)
    with pytest.raises(GenerationError):
        h.orch.apply_owner_action(
            _action(OwnerDecision.CONFIRM, OwnerInteractionKind.CLASSIFICATION), now=T0
        )
    assert h.repo.get_request("req-1").state is RequestState.FAILED
