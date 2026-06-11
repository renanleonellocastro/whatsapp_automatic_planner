"""Unit tests for the SMTP email notifier (AD-3, FR-DLV-01)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from email.message import EmailMessage

from wapp_planner.domain.enums import Channel
from wapp_planner.providers.base import Attachment, OutboundMessage
from wapp_planner.providers.email_notifier import EmailNotifier


class _FakeSMTP:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def send_message(self, message: EmailMessage) -> None:
        self.sent.append(message)


def _notifier() -> tuple[EmailNotifier, _FakeSMTP]:
    smtp = _FakeSMTP()

    @contextmanager
    def connect() -> Iterator[_FakeSMTP]:
        yield smtp

    return EmailNotifier(connect, sender="owner@company.com"), smtp


def test_channel_is_email() -> None:
    notifier, _ = _notifier()
    assert notifier.channel is Channel.EMAIL


def test_send_plain_message() -> None:
    notifier, smtp = _notifier()
    msg_id = notifier.send(
        OutboundMessage(recipient="to@x.com", body="hello", subject="New request")
    )
    assert msg_id.startswith("<")
    sent = smtp.sent[0]
    assert sent["To"] == "to@x.com"
    assert sent["From"] == "owner@company.com"
    assert sent["Subject"] == "New request"
    assert "hello" in sent.get_content()


def test_send_without_subject_uses_placeholder() -> None:
    notifier, smtp = _notifier()
    notifier.send(OutboundMessage(recipient="to@x.com", body="b"))
    assert smtp.sent[0]["Subject"] == "(no subject)"


def test_send_with_attachments() -> None:
    notifier, smtp = _notifier()
    att = Attachment(filename="quote.pdf", content=b"%PDF", content_type="application/pdf")
    notifier.send(OutboundMessage(recipient="to@x.com", body="doc", attachments=[att]))
    attachments = list(smtp.sent[0].iter_attachments())
    assert attachments[0].get_filename() == "quote.pdf"
