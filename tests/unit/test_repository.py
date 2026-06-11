"""Unit tests for the in-memory request repository (NFR-DURAB-01/IDEMP-01)."""

from __future__ import annotations

from wapp_planner.domain.enums import OwnerDecision, OwnerInteractionKind
from wapp_planner.domain.models import DocumentRevision, Message, OwnerInteraction, Request
from wapp_planner.persistence.repository import InMemoryRequestRepository
from wapp_planner.workflow.enums import MessageType


def test_request_save_and_get() -> None:
    repo = InMemoryRequestRepository()
    assert repo.get_request("r1") is None
    repo.save_request(Request(id="r1", client_id="c1"))
    assert repo.get_request("r1").id == "r1"


def test_messages_roundtrip() -> None:
    repo = InMemoryRequestRepository()
    assert repo.get_messages("r1") == []
    repo.set_messages("r1", [Message(id="m1", type=MessageType.TEXT, order=0)])
    assert [m.id for m in repo.get_messages("r1")] == ["m1"]


def test_revisions_and_latest() -> None:
    repo = InMemoryRequestRepository()
    assert repo.get_revisions("r1") == []
    assert repo.latest_revision("r1") is None
    repo.add_revision(DocumentRevision(id="d1", request_id="r1", revision_no=1))
    repo.add_revision(DocumentRevision(id="d2", request_id="r1", revision_no=2))
    assert [r.revision_no for r in repo.get_revisions("r1")] == [1, 2]
    assert repo.latest_revision("r1").revision_no == 2


def test_record_interaction_is_idempotent() -> None:
    repo = InMemoryRequestRepository()
    interaction = OwnerInteraction(
        id="i1",
        request_id="r1",
        kind=OwnerInteractionKind.CLASSIFICATION,
        decision=OwnerDecision.CONFIRM,
    )
    assert repo.record_interaction(interaction) is True
    assert repo.record_interaction(interaction) is False
