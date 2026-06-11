"""SMTP/SES email notifier (AD-3, FR-DLV-01).

Builds a MIME message (with attachments) and sends it over an injected SMTP
connection factory, so it is unit-tested with a fake SMTP — no network. Use
:func:`build_smtp_connect` in production to connect to a real server.
"""

from __future__ import annotations

import smtplib
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Any, Protocol

from wapp_planner.domain.enums import Channel
from wapp_planner.providers.base import Notifier, OutboundMessage


class _SMTPLike(Protocol):  # pragma: no cover - structural typing only
    def send_message(self, message: EmailMessage) -> Any: ...


SmtpConnect = Callable[[], AbstractContextManager[_SMTPLike]]


class EmailNotifier(Notifier):
    """Sends owner emails via an injected SMTP connection factory."""

    channel = Channel.EMAIL

    def __init__(self, connect: SmtpConnect, *, sender: str) -> None:
        self._connect = connect
        self._sender = sender

    def send(self, message: OutboundMessage) -> str:
        mime = EmailMessage()
        mime["From"] = self._sender
        mime["To"] = message.recipient
        mime["Subject"] = message.subject or "(no subject)"
        message_id = make_msgid()
        mime["Message-ID"] = message_id
        mime.set_content(message.body)
        for attachment in message.attachments:
            maintype, _, subtype = attachment.content_type.partition("/")
            mime.add_attachment(
                attachment.content,
                maintype=maintype,
                subtype=subtype or "octet-stream",
                filename=attachment.filename,
            )
        with self._connect() as smtp:
            smtp.send_message(mime)
        return message_id


def build_smtp_connect(  # pragma: no cover - real network connection
    *, host: str, port: int, username: str, password: str
) -> SmtpConnect:
    """Return a connection factory that opens a TLS SMTP session and logs in."""

    @contextmanager
    def _connect() -> Iterator[smtplib.SMTP]:
        client = smtplib.SMTP(host, port)
        try:
            client.starttls()
            client.login(username, password)
            yield client
        finally:
            client.quit()

    return _connect
