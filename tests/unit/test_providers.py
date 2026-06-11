"""Unit tests for provider DTOs and in-memory fakes."""

from __future__ import annotations

import pytest

from wapp_planner.domain.enums import Channel
from wapp_planner.providers.base import (
    Attachment,
    DownloadedMedia,
    LLMResult,
    OutboundMessage,
    TranscriptionResult,
)
from wapp_planner.providers.fakes import (
    FakeLLMProvider,
    FakeTranscriptionProvider,
    FakeVisionProvider,
    FakeWhatsAppMediaClient,
    InMemoryStorage,
    RecordingNotifier,
)


# ── DTOs ────────────────────────────────────────────────────────────────
def test_downloaded_media_size() -> None:
    media = DownloadedMedia(content=b"abcde", mime_type="audio/ogg")
    assert media.size == 5


def test_outbound_message_defaults() -> None:
    msg = OutboundMessage(recipient="owner@x.com", body="hi")
    assert msg.subject is None
    assert msg.attachments == []


def test_attachment_and_results_models() -> None:
    att = Attachment(filename="quote.pdf", content=b"%PDF", content_type="application/pdf")
    assert att.filename == "quote.pdf"
    assert LLMResult(text="t", model="m").cost_usd == 0.0
    assert TranscriptionResult(text="t", model="m").language is None


# ── FakeLLMProvider ─────────────────────────────────────────────────────
def test_fake_llm_default_response() -> None:
    llm = FakeLLMProvider(default_text="hello", cost_per_call=0.01)
    result = llm.complete(system="s", user="u", model="gpt-4o", temperature=0.2, max_tokens=10)
    assert result.text == "hello"
    assert result.model == "gpt-4o"
    assert result.cost_usd == 0.01
    assert llm.calls[0] == {
        "system": "s",
        "user": "u",
        "model": "gpt-4o",
        "temperature": 0.2,
        "max_tokens": 10,
    }


def test_fake_llm_scripted_responses_consumed_in_order() -> None:
    scripted = [LLMResult(text="first", model="m"), LLMResult(text="second", model="m")]
    llm = FakeLLMProvider(responses=scripted)
    assert llm.complete(system="s", user="u", model="m").text == "first"
    assert llm.complete(system="s", user="u", model="m").text == "second"
    # exhausted -> default
    assert llm.complete(system="s", user="u", model="m").text == ""


# ── FakeTranscriptionProvider ───────────────────────────────────────────
def test_fake_transcription_default_and_scripted() -> None:
    tx = FakeTranscriptionProvider(default_text="spoken")
    assert tx.transcribe(b"xx", model="w").text == "spoken"
    tx2 = FakeTranscriptionProvider(
        results=[TranscriptionResult(text="one", model="w", language="en")]
    )
    res = tx2.transcribe(b"xx", model="w", mime_type="audio/ogg")
    assert res.text == "one"
    assert tx2.calls[0]["mime_type"] == "audio/ogg"


# ── FakeVisionProvider ──────────────────────────────────────────────────
def test_fake_vision_default_and_scripted() -> None:
    vis = FakeVisionProvider(default="a wall")
    assert vis.describe(b"img", model="m", mime_type="image/jpeg", prompt="describe") == "a wall"
    vis2 = FakeVisionProvider(descriptions=["a pipe"])
    assert vis2.describe(b"img", model="m", mime_type="image/jpeg", prompt="p") == "a pipe"
    assert vis2.calls[0]["prompt"] == "p"


# ── InMemoryStorage ─────────────────────────────────────────────────────
def test_in_memory_storage_roundtrip() -> None:
    store = InMemoryStorage()
    ref = store.put("k1", b"data", content_type="text/plain")
    assert ref == "memory://k1"
    assert store.exists("k1")
    assert store.get("k1") == b"data"
    assert store.content_type("k1") == "text/plain"


def test_in_memory_storage_missing_key() -> None:
    store = InMemoryStorage()
    assert not store.exists("nope")
    with pytest.raises(KeyError):
        store.get("nope")
    with pytest.raises(KeyError):
        store.content_type("nope")


def test_in_memory_storage_delete_is_idempotent() -> None:
    store = InMemoryStorage()
    store.put("k1", b"x", content_type="text/plain")
    store.delete("k1")
    assert not store.exists("k1")
    store.delete("k1")  # no error on second delete


# ── RecordingNotifier ───────────────────────────────────────────────────
def test_recording_notifier_sends_and_ids_increment() -> None:
    notifier = RecordingNotifier(Channel.EMAIL)
    id1 = notifier.send(OutboundMessage(recipient="o@x.com", body="a"))
    id2 = notifier.send(OutboundMessage(recipient="o@x.com", body="b"))
    assert (id1, id2) == ("email-msg-1", "email-msg-2")
    assert [m.body for m in notifier.sent] == ["a", "b"]


def test_recording_notifier_failure_injection() -> None:
    notifier = RecordingNotifier(Channel.WHATSAPP, raise_on_send=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="boom"):
        notifier.send(OutboundMessage(recipient="+1", body="x"))
    assert notifier.sent == []


# ── FakeWhatsAppMediaClient ─────────────────────────────────────────────
def test_fake_whatsapp_media_add_and_download() -> None:
    client = FakeWhatsAppMediaClient()
    client.add("media-1", b"bytes", "audio/ogg")
    media = client.download("media-1")
    assert media.content == b"bytes"
    assert media.mime_type == "audio/ogg"


def test_fake_whatsapp_media_preloaded_and_missing() -> None:
    client = FakeWhatsAppMediaClient({"m": DownloadedMedia(content=b"x", mime_type="image/jpeg")})
    assert client.download("m").mime_type == "image/jpeg"
    with pytest.raises(KeyError):
        client.download("unknown")
