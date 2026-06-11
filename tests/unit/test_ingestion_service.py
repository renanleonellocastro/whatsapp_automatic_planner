"""Unit tests for the ingestion service (FR-ING-*)."""

from __future__ import annotations

import hashlib
import hmac
import itertools
import json
from datetime import timedelta

import pytest

from tests import fixtures as fx
from tests.unit.test_orchestrator import T0, _Harness, _harness
from wapp_planner.aggregation.aggregator import Aggregator
from wapp_planner.domain.enums import Channel
from wapp_planner.domain.models import Client
from wapp_planner.ingestion.client_registry import ClientRegistry
from wapp_planner.ingestion.idempotency import InMemoryIdempotencyStore
from wapp_planner.ingestion.media_downloader import MediaDownloader
from wapp_planner.ingestion.service import IngestionService, InvalidPayloadError, SignatureError
from wapp_planner.ingestion.signature import WebhookVerificationError
from wapp_planner.providers.fakes import FakeWhatsAppMediaClient
from wapp_planner.workflow.enums import RequestState

SECRET = "app-secret"


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def build_ingestion() -> tuple[IngestionService, _Harness, FakeWhatsAppMediaClient]:
    h = _harness()
    media_client = FakeWhatsAppMediaClient()
    downloader = MediaDownloader(media_client, h.storage, max_bytes=10_000)
    counter = itertools.count(1)
    aggregator = Aggregator(
        inactivity_seconds=90,
        max_duration_seconds=600,
        id_factory=lambda: f"req-{next(counter)}",
    )
    registry = ClientRegistry([Client(id="c1", name="Bob Builder", phone_numbers=["15551230000"])])
    service = IngestionService(
        app_secret=SECRET,
        verify_token="vt",
        idempotency=InMemoryIdempotencyStore(),
        media_downloader=downloader,
        storage=h.storage,
        aggregator=aggregator,
        orchestrator=h.orch,
        registry=registry,
    )
    return service, h, media_client


def _body(messages: list[dict[str, object]], **kw: object) -> bytes:
    return json.dumps(fx.webhook(messages, **kw)).encode()


# ── verification & signature ────────────────────────────────────────────
def test_verify_subscription_ok_and_fail() -> None:
    service, _, _ = build_ingestion()
    assert service.verify_subscription("subscribe", "vt", "chal") == "chal"
    with pytest.raises(WebhookVerificationError):
        service.verify_subscription("subscribe", "wrong", "chal")


def test_receive_rejects_bad_signature() -> None:
    service, _, _ = build_ingestion()
    with pytest.raises(SignatureError):
        service.receive(_body([fx.text_message()]), "sha256=deadbeef", now=T0)


def test_receive_rejects_non_json_body() -> None:
    service, _, _ = build_ingestion()
    body = b"not json"
    with pytest.raises(InvalidPayloadError):
        service.receive(body, sign(body), now=T0)


# ── aggregation + processing ──────────────────────────────────────────────
def test_text_message_aggregated_then_flushed() -> None:
    service, h, _ = build_ingestion()
    body = _body([fx.text_message("need a quote")])
    assert service.receive(body, sign(body), now=T0) == 1
    assert h.repo.get_request("req-1") is None  # not processed until window closes

    processed = service.flush_due(T0 + timedelta(seconds=200))
    assert processed == 1
    request = h.repo.get_request("req-1")
    assert request.state is RequestState.AWAITING_CLASSIFICATION
    assert len(h.notifiers[Channel.EMAIL].sent) == 1


def test_duplicate_message_id_ignored() -> None:
    service, _, _ = build_ingestion()
    body = _body([fx.text_message(mid="dup")])
    assert service.receive(body, sign(body), now=T0) == 1
    assert service.receive(body, sign(body), now=T0) == 0  # idempotent


def test_new_message_after_window_displaces_and_processes_previous() -> None:
    service, h, _ = build_ingestion()
    b1 = _body([fx.text_message("first", mid="a")])
    service.receive(b1, sign(b1), now=T0)
    b2 = _body([fx.text_message("second", mid="b")])
    service.receive(b2, sign(b2), now=T0 + timedelta(seconds=200))  # displaces bucket 1
    assert h.repo.get_request("req-1").state is RequestState.AWAITING_CLASSIFICATION
    assert len(h.notifiers[Channel.EMAIL].sent) == 1


def test_media_message_downloaded_and_processed() -> None:
    service, h, media_client = build_ingestion()
    media_client.add("media-audio-1", b"voice-bytes", "audio/ogg")
    body = _body([fx.audio_message()])
    service.receive(body, sign(body), now=T0)
    service.flush_due(T0 + timedelta(seconds=200))
    request = h.repo.get_request("req-1")
    assert request.state is RequestState.AWAITING_CLASSIFICATION
    assert "spoken" in request.normalized_transcript  # transcription ran


def test_media_download_failure_degrades_but_still_processes() -> None:
    service, h, _ = build_ingestion()  # media client has no media -> download raises
    body = _body([fx.audio_message()])
    service.receive(body, sign(body), now=T0)
    service.flush_due(T0 + timedelta(seconds=200))
    request = h.repo.get_request("req-1")
    assert request is not None
    assert "unprocessable" in request.normalized_transcript


def test_unknown_client_is_flagged() -> None:
    service, h, _ = build_ingestion()
    msg = fx.text_message()
    msg["from"] = "14040000000"  # not in registry
    body = _body([msg], contacts=[{"wa_id": "14040000000", "profile": {"name": "Stranger"}}])
    service.receive(body, sign(body), now=T0)
    service.flush_due(T0 + timedelta(seconds=200))
    request = h.repo.get_request("req-1")
    assert "unknown_client" in request.flags
    assert request.client_name == "14040000000"
