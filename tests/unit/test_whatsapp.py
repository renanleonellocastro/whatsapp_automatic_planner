"""Unit tests for the WhatsApp Graph adapters (AD-1, FR-ING-07, FR-DLV-01)."""

from __future__ import annotations

import httpx
import pytest

from wapp_planner.providers.base import Attachment, OutboundMessage
from wapp_planner.providers.whatsapp import WhatsAppGraphMediaClient, WhatsAppNotifier

API = "https://graph.test/v20"


def _client(handler: object) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]


def test_media_download_two_step() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/media-1"):
            return httpx.Response(
                200, json={"url": "https://dl.test/file", "mime_type": "audio/ogg"}
            )
        return httpx.Response(200, content=b"voice-bytes")

    client = WhatsAppGraphMediaClient(_client(handler), access_token="tok", api_base=API)
    media = client.download("media-1")
    assert media.content == b"voice-bytes"
    assert media.mime_type == "audio/ogg"


def test_media_download_mime_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/media-2"):
            return httpx.Response(200, json={"url": "https://dl.test/f2"})
        return httpx.Response(200, content=b"x")

    client = WhatsAppGraphMediaClient(_client(handler), access_token="tok", api_base=API)
    assert client.download("media-2").mime_type == "application/octet-stream"


def test_media_download_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "nope"})

    client = WhatsAppGraphMediaClient(_client(handler), access_token="tok", api_base=API)
    with pytest.raises(httpx.HTTPStatusError):
        client.download("missing")


def test_notifier_sends_text() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"messages": [{"id": "wamid.out"}]})

    notifier = WhatsAppNotifier(
        _client(handler), access_token="tok", phone_number_id="PID", api_base=API
    )
    msg_id = notifier.send(OutboundMessage(recipient="+15550001111", body="hello"))
    assert msg_id == "wamid.out"
    assert captured["auth"] == "Bearer tok"
    assert captured["body"]["text"]["body"] == "hello"


def test_notifier_notes_attachments() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)["text"]["body"]
        assert "quote.pdf" in body
        return httpx.Response(200, json={"messages": [{"id": "x"}]})

    notifier = WhatsAppNotifier(
        _client(handler), access_token="tok", phone_number_id="PID", api_base=API
    )
    att = Attachment(filename="quote.pdf", content=b"%PDF", content_type="application/pdf")
    notifier.send(OutboundMessage(recipient="+1", body="doc ready", attachments=[att]))


def test_notifier_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    notifier = WhatsAppNotifier(
        _client(handler), access_token="tok", phone_number_id="PID", api_base=API
    )
    with pytest.raises(httpx.HTTPStatusError):
        notifier.send(OutboundMessage(recipient="+1", body="x"))
