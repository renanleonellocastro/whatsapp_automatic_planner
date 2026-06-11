"""Unit tests for the time source."""

from __future__ import annotations

from datetime import UTC, datetime

from wapp_planner import clock


def test_now_is_timezone_aware_utc() -> None:
    before = datetime.now(UTC)
    value = clock.now()
    after = datetime.now(UTC)
    assert value.tzinfo is UTC
    assert before <= value <= after
