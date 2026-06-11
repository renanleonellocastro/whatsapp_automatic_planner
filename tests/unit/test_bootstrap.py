"""Unit tests for the composition root (DEP-01/04)."""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from tests.unit.test_ingestion_service import build_ingestion
from tests.unit.test_orchestrator import QUOTE_CLS, T0
from wapp_planner.bootstrap import Adapters, FlushWorker, build_app
from wapp_planner.config.settings import Secrets, Settings
from wapp_planner.domain.enums import Channel
from wapp_planner.domain.models import Client
from wapp_planner.media.extractors import FakeDocumentTextExtractor, FakeVideoProcessor
from wapp_planner.providers.fakes import (
    FakeLLMProvider,
    FakeTranscriptionProvider,
    FakeVisionProvider,
    FakeWhatsAppMediaClient,
    InMemoryStorage,
    RecordingNotifier,
)

SECRET_KW = {
    "openai_api_key": "sk",
    "whatsapp_access_token": "tok",
    "whatsapp_phone_number_id": "pid",
    "whatsapp_verify_token": "vt",
    "whatsapp_app_secret": "secret",
    "smtp_host": "smtp.x",
    "smtp_username": "u",
    "smtp_password": "p",
}


def _adapters() -> Adapters:
    return Adapters(
        llm=FakeLLMProvider(default_text=QUOTE_CLS),
        transcriber=FakeTranscriptionProvider(default_text="spoken"),
        vision=FakeVisionProvider(default="img"),
        video=FakeVideoProcessor(),
        documents=FakeDocumentTextExtractor(),
        storage=InMemoryStorage(),
        media_client=FakeWhatsAppMediaClient(),
        notifiers={
            Channel.EMAIL: RecordingNotifier(Channel.EMAIL),
            Channel.WHATSAPP: RecordingNotifier(Channel.WHATSAPP),
        },
    )


def test_build_app_both_channels() -> None:
    settings = Settings(
        owner_email="o@x.com",
        owner_whatsapp="+15550000000",
        notify_channel=Channel.EMAIL,
        deliver_channel=Channel.WHATSAPP,
    )
    app = build_app(
        settings, Secrets(**SECRET_KW), _adapters(), clients=[Client(id="c1", name="Bob")]
    )
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    ok = client.get(
        "/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "z"},
    )
    assert ok.text == "z"


def test_build_app_email_only() -> None:
    settings = Settings(
        owner_email="o@x.com", notify_channel=Channel.EMAIL, deliver_channel=Channel.EMAIL
    )
    app = build_app(settings, Secrets(**SECRET_KW), _adapters())
    assert TestClient(app).get("/health").status_code == 200


def test_build_app_whatsapp_only() -> None:
    settings = Settings(
        owner_whatsapp="+15550000000",
        notify_channel=Channel.WHATSAPP,
        deliver_channel=Channel.WHATSAPP,
    )
    app = build_app(settings, Secrets(**SECRET_KW), _adapters())
    assert TestClient(app).get("/health").status_code == 200


def test_flush_worker_tick_processes_due_buckets() -> None:
    service, _h, _ = build_ingestion()
    import hashlib
    import hmac
    import json

    from tests import fixtures as fx

    body = json.dumps(fx.webhook([fx.text_message("need a quote")])).encode()
    sig = "sha256=" + hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
    service.receive(body, sig, now=T0)

    worker = FlushWorker(
        service, interval_seconds=1.0, sleep=lambda _: None, now=lambda: T0 + timedelta(seconds=200)
    )
    assert worker.tick() == 1
    assert worker.tick() == 0  # nothing left
