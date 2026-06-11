"""Unit tests for media download + storage (FR-ING-07, NFR-SEC-02)."""

from __future__ import annotations

import pytest

from wapp_planner.ingestion.media_downloader import (
    MediaDownloader,
    MediaRejectedError,
    MediaTooLargeError,
)
from wapp_planner.providers.fakes import FakeWhatsAppMediaClient, InMemoryStorage


def _downloader(
    max_bytes: int = 1000,
) -> tuple[MediaDownloader, FakeWhatsAppMediaClient, InMemoryStorage]:
    client = FakeWhatsAppMediaClient()
    storage = InMemoryStorage()
    return MediaDownloader(client, storage, max_bytes=max_bytes), client, storage


def test_fetch_and_store_happy_path() -> None:
    downloader, client, storage = _downloader()
    client.add("media-1", b"audio-bytes", "audio/ogg")
    stored = downloader.fetch_and_store(request_id="r1", message_id="m1", media_id="media-1")
    assert stored.key == "r1/m1"
    assert stored.ref == "memory://r1/m1"
    assert stored.mime_type == "audio/ogg"
    assert stored.size == len(b"audio-bytes")
    assert storage.get("r1/m1") == b"audio-bytes"


def test_oversized_media_rejected_before_storing() -> None:
    downloader, client, storage = _downloader(max_bytes=4)
    client.add("media-1", b"too-large", "image/jpeg")
    with pytest.raises(MediaTooLargeError):
        downloader.fetch_and_store(request_id="r1", message_id="m1", media_id="media-1")
    assert not storage.exists("r1/m1")


def test_disallowed_mime_rejected() -> None:
    downloader, client, storage = _downloader()
    client.add("media-1", b"x", "application/x-msdownload")
    with pytest.raises(MediaRejectedError):
        downloader.fetch_and_store(request_id="r1", message_id="m1", media_id="media-1")
    assert not storage.exists("r1/m1")


def test_unknown_media_id_propagates() -> None:
    downloader, _client, _storage = _downloader()
    with pytest.raises(KeyError):
        downloader.fetch_and_store(request_id="r1", message_id="m1", media_id="missing")


def test_allowed_prefixes_cover_documents_and_video() -> None:
    downloader, client, _ = _downloader()
    client.add("pdf", b"%PDF", "application/pdf")
    client.add("vid", b"v", "video/mp4")
    assert downloader.fetch_and_store(request_id="r", message_id="d", media_id="pdf").mime_type == (
        "application/pdf"
    )
    assert downloader.fetch_and_store(request_id="r", message_id="v", media_id="vid").mime_type == (
        "video/mp4"
    )
