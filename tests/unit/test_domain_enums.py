"""Unit tests for domain enums."""

from __future__ import annotations

import pytest

from wapp_planner.domain.enums import (
    Channel,
    OwnerDecision,
    OwnerInteractionKind,
    ProcessingStatus,
)


@pytest.mark.parametrize(
    ("channel", "target", "expected"),
    [
        (Channel.BOTH, Channel.EMAIL, True),
        (Channel.BOTH, Channel.WHATSAPP, True),
        (Channel.BOTH, Channel.BOTH, True),
        (Channel.EMAIL, Channel.EMAIL, True),
        (Channel.EMAIL, Channel.WHATSAPP, False),
        (Channel.EMAIL, Channel.BOTH, False),
        (Channel.WHATSAPP, Channel.WHATSAPP, True),
        (Channel.WHATSAPP, Channel.EMAIL, False),
    ],
)
def test_channel_includes(channel: Channel, target: Channel, expected: bool) -> None:
    assert channel.includes(target) is expected


def test_enum_member_sets() -> None:
    assert {s.value for s in ProcessingStatus} == {"pending", "processed", "unprocessable"}
    assert {k.value for k in OwnerInteractionKind} == {"classification", "approval"}
    assert {d.value for d in OwnerDecision} == {
        "confirm",
        "correct",
        "reject",
        "approve",
        "revise",
    }
