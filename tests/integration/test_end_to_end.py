"""End-to-end integration test through the whole pipeline with fakes (TST-02/08).

Exercises the real token round-trip: ingest → owner clicks the link in the
notification body → resolve_action → apply, all the way to COMPLETED, plus the
revision loop. No real WhatsApp/OpenAI/AWS — only the in-memory fakes.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tests.unit.test_orchestrator import _aggregated, _harness
from wapp_planner.domain.enums import Channel
from wapp_planner.workflow.enums import RequestState

T0 = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)


def _token(body: str, label: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"- {label}:"):
            return stripped.split("token=")[1]
    raise AssertionError(f"no {label!r} link found in body")


def test_quote_confirm_then_approve_completes() -> None:
    h = _harness()
    request = h.orch.ingest(_aggregated(), {}, client_name="Bob", now=T0)
    assert request.state is RequestState.AWAITING_CLASSIFICATION

    # Owner clicks "Confirm" in the email notification.
    confirm_token = _token(h.notifiers[Channel.EMAIL].sent[-1].body, "Confirm")
    confirm = h.notify.resolve_action(confirm_token, now=T0)
    request = h.orch.apply_owner_action(confirm, now=T0)
    assert request.state is RequestState.AWAITING_APPROVAL

    # Owner clicks "Approve" in the WhatsApp delivery.
    approve_token = _token(h.notifiers[Channel.WHATSAPP].sent[-1].body, "Approve")
    approve = h.notify.resolve_action(approve_token, now=T0)
    request = h.orch.apply_owner_action(approve, now=T0)
    assert request.state is RequestState.COMPLETED

    # A PDF + DOCX were produced and stored.
    delivered = h.notifiers[Channel.WHATSAPP].sent[0]
    assert {a.content_type for a in delivered.attachments} == {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }


def test_quote_confirm_then_revise_then_approve() -> None:
    h = _harness()
    h.orch.ingest(_aggregated(), {}, client_name="Bob", now=T0)
    confirm = h.notify.resolve_action(
        _token(h.notifiers[Channel.EMAIL].sent[-1].body, "Confirm"), now=T0
    )
    h.orch.apply_owner_action(confirm, now=T0)

    # First delivery → owner asks for a revision with feedback.
    revise = h.notify.resolve_action(
        _token(h.notifiers[Channel.WHATSAPP].sent[-1].body, "Request revision"),
        now=T0,
        feedback="reduce the demolition cost",
    )
    request = h.orch.apply_owner_action(revise, now=T0)
    assert request.state is RequestState.AWAITING_APPROVAL
    assert request.current_revision == 2

    # Second delivery → owner approves.
    approve = h.notify.resolve_action(
        _token(h.notifiers[Channel.WHATSAPP].sent[-1].body, "Approve"), now=T0
    )
    request = h.orch.apply_owner_action(approve, now=T0)
    assert request.state is RequestState.COMPLETED

    revisions = h.repo.get_revisions("req-1")
    assert [r.revision_no for r in revisions] == [1, 2]
    assert revisions[1].feedback == "reduce the demolition cost"


def test_correct_intent_then_confirm_path() -> None:
    h = _harness()
    h.orch.ingest(_aggregated(), {}, client_name="Bob", now=T0)

    # Owner says "It's an execution plan" instead of a quote.
    correct = h.notify.resolve_action(
        _token(h.notifiers[Channel.EMAIL].sent[-1].body, "It's an execution plan"), now=T0
    )
    request = h.orch.apply_owner_action(correct, now=T0)
    assert request.state is RequestState.AWAITING_CLASSIFICATION
    assert request.intent.value == "execution_plan"
    # a fresh confirm link was sent in the re-notification (resolves cleanly)
    confirm = h.notify.resolve_action(
        _token(h.notifiers[Channel.EMAIL].sent[-1].body, "Confirm"), now=T0
    )
    assert confirm.request_id == "req-1"
    assert len(h.notifiers[Channel.EMAIL].sent) == 2  # original + re-notification
