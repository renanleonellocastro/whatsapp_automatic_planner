"""Unit tests for message aggregation (FR-AGG-*)."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from wapp_planner.aggregation.aggregator import Aggregator
from wapp_planner.domain.models import Message
from wapp_planner.workflow.enums import MessageType

T0 = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)


def _ids() -> Callable[[], str]:
    counter = itertools.count(1)
    return lambda: f"req-{next(counter)}"


def _agg(inactivity: int = 90, max_duration: int = 600) -> Aggregator:
    return Aggregator(
        inactivity_seconds=inactivity,
        max_duration_seconds=max_duration,
        id_factory=_ids(),
    )


def _msg(mid: str, body: str = "x") -> Message:
    return Message(id=mid, type=MessageType.TEXT, order=0, text=body)


def _at(seconds: int) -> datetime:
    return T0 + timedelta(seconds=seconds)


def test_single_message_opens_a_bucket() -> None:
    agg = _agg()
    assert agg.add("c1", _msg("m1"), T0) is None
    assert agg.open_count == 1


def test_messages_within_inactivity_share_a_bucket_with_order() -> None:
    agg = _agg()
    agg.add("c1", _msg("m1"), _at(0))
    agg.add("c1", _msg("m2"), _at(30))
    assert agg.open_count == 1
    [req] = agg.flush_all()
    assert [m.id for m in req.messages] == ["m1", "m2"]
    assert [m.order for m in req.messages] == [0, 1]
    assert req.request_id == "req-1"


def test_inactivity_boundary_starts_new_bucket() -> None:
    agg = _agg(inactivity=90)
    agg.add("c1", _msg("m1"), _at(0))
    # exactly 90s later: not < 90 -> closes the old bucket, opens a new one
    displaced = agg.add("c1", _msg("m2"), _at(90))
    assert displaced is not None
    assert [m.id for m in displaced.messages] == ["m1"]
    assert agg.open_count == 1


def test_max_duration_caps_a_chatty_bucket() -> None:
    agg = _agg(inactivity=60, max_duration=100)
    agg.add("c1", _msg("m1"), _at(0))
    agg.add("c1", _msg("m2"), _at(50))  # active: within both windows
    agg.add("c1", _msg("m3"), _at(90))  # active
    # 130s: idle gap (40s) is fine but total duration (130s) exceeds max=100
    displaced = agg.add("c1", _msg("m4"), _at(130))
    assert displaced is not None
    assert [m.id for m in displaced.messages] == ["m1", "m2", "m3"]


def test_flush_due_closes_idle_buckets_only() -> None:
    agg = _agg(inactivity=90)
    agg.add("c1", _msg("m1"), _at(0))
    assert agg.flush_due(_at(30)) == []  # still active
    closed = agg.flush_due(_at(120))  # idle past inactivity
    assert len(closed) == 1
    assert agg.open_count == 0


def test_flush_all_closes_every_client() -> None:
    agg = _agg()
    agg.add("c1", _msg("m1"), T0)
    agg.add("c2", _msg("m2"), T0)
    closed = agg.flush_all()
    assert {r.client_id for r in closed} == {"c1", "c2"}
    assert agg.open_count == 0


def test_clients_are_independent() -> None:
    agg = _agg()
    agg.add("c1", _msg("m1"), _at(0))
    agg.add("c2", _msg("m2"), _at(200))  # would expire c1 only if shared
    assert agg.open_count == 2


def test_state_export_and_restore_survives_restart() -> None:
    agg = _agg()
    agg.add("c1", _msg("m1"), _at(0))
    agg.add("c1", _msg("m2"), _at(10))
    snapshot = agg.export_state()

    restored = _agg()
    restored.load_state(snapshot)
    assert restored.open_count == 1
    [req] = restored.flush_all()
    assert [m.id for m in req.messages] == ["m1", "m2"]
