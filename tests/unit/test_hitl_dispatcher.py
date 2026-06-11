"""Unit tests for the channel dispatcher (AD-3)."""

from __future__ import annotations

import pytest

from wapp_planner.domain.enums import Channel
from wapp_planner.hitl.dispatcher import ChannelDispatcher, ChannelTarget, MissingNotifierError
from wapp_planner.providers.base import Attachment
from wapp_planner.providers.fakes import RecordingNotifier


def _dispatcher(*channels: Channel) -> tuple[ChannelDispatcher, dict[Channel, RecordingNotifier]]:
    notifiers = {c: RecordingNotifier(c) for c in channels}
    targets = {
        c: ChannelTarget(notifier=n, recipient=f"to-{c.value}") for c, n in notifiers.items()
    }
    return ChannelDispatcher(targets), notifiers


def test_send_email_only() -> None:
    dispatcher, notifiers = _dispatcher(Channel.EMAIL, Channel.WHATSAPP)
    result = dispatcher.send(Channel.EMAIL, body="hi", subject="s")
    assert set(result) == {Channel.EMAIL}
    assert len(notifiers[Channel.EMAIL].sent) == 1
    assert notifiers[Channel.WHATSAPP].sent == []
    assert notifiers[Channel.EMAIL].sent[0].recipient == "to-email"


def test_send_both_fans_out() -> None:
    dispatcher, notifiers = _dispatcher(Channel.EMAIL, Channel.WHATSAPP)
    result = dispatcher.send(Channel.BOTH, body="hi")
    assert set(result) == {Channel.EMAIL, Channel.WHATSAPP}
    assert len(notifiers[Channel.WHATSAPP].sent) == 1


def test_send_whatsapp_only() -> None:
    dispatcher, notifiers = _dispatcher(Channel.EMAIL, Channel.WHATSAPP)
    dispatcher.send(Channel.WHATSAPP, body="hi")
    assert notifiers[Channel.EMAIL].sent == []
    assert len(notifiers[Channel.WHATSAPP].sent) == 1


def test_missing_notifier_raises() -> None:
    dispatcher, _ = _dispatcher(Channel.EMAIL)  # no whatsapp target
    with pytest.raises(MissingNotifierError, match="whatsapp"):
        dispatcher.send(Channel.BOTH, body="hi")


def test_attachments_passed_through() -> None:
    dispatcher, notifiers = _dispatcher(Channel.EMAIL)
    att = Attachment(filename="q.pdf", content=b"%PDF", content_type="application/pdf")
    dispatcher.send(Channel.EMAIL, body="b", attachments=[att])
    assert notifiers[Channel.EMAIL].sent[0].attachments == [att]
