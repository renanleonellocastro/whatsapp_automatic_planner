"""Integration tests for the FastAPI HTTP surface (DEP-02/04)."""

from __future__ import annotations

import json
from datetime import timedelta

from fastapi.testclient import TestClient

from tests import fixtures as fx
from tests.unit.test_ingestion_service import build_ingestion, sign
from tests.unit.test_orchestrator import T0
from wapp_planner.api.app import AppContext, create_app
from wapp_planner.domain.enums import Channel, OwnerDecision, OwnerInteractionKind
from wapp_planner.hitl.tokens import TokenSigner


def _setup() -> tuple[TestClient, object, object]:
    service, h, _ = build_ingestion()
    ctx = AppContext(ingestion=service, notifications=h.notify, orchestrator=h.orch, now=lambda: T0)
    return TestClient(create_app(ctx)), service, h


def _text_body(text: str = "need a quote") -> bytes:
    return json.dumps(fx.webhook([fx.text_message(text)])).encode()


def _token_from(body: str, label: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"- {label}:"):
            return stripped.split("token=")[1]
    raise AssertionError(f"no {label!r} link")


def test_health() -> None:
    client, _, _ = _setup()
    assert client.get("/health").json() == {"status": "ok"}


def test_verify_subscription() -> None:
    client, _, _ = _setup()
    ok = client.get(
        "/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "xyz"},
    )
    assert ok.status_code == 200
    assert ok.text == "xyz"

    bad = client.get(
        "/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "xyz"},
    )
    assert bad.status_code == 403


def test_inbound_accepts_signed_payload() -> None:
    client, _, _ = _setup()
    body = _text_body()
    resp = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sign(body)})
    assert resp.status_code == 200
    assert resp.json() == {"accepted": 1}


def test_inbound_rejects_bad_signature() -> None:
    client, _, _ = _setup()
    body = _text_body()
    resp = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": "sha256=bad"})
    assert resp.status_code == 403


def test_inbound_rejects_bad_payload() -> None:
    client, _, _ = _setup()
    resp = client.post(
        "/webhook", content=b"not json", headers={"X-Hub-Signature-256": sign(b"not json")}
    )
    assert resp.status_code == 400


def test_hitl_action_confirm_advances_state() -> None:
    client, service, h = _setup()
    body = _text_body()
    client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sign(body)})
    service.flush_due(T0 + timedelta(seconds=200))

    token = _token_from(h.notifiers[Channel.EMAIL].sent[-1].body, "Confirm")
    resp = client.get("/hitl/action", params={"token": token})
    assert resp.status_code == 200
    assert resp.json() == {"request_id": "req-1", "state": "awaiting_approval"}


def test_hitl_action_invalid_token() -> None:
    client, _, _ = _setup()
    resp = client.get("/hitl/action", params={"token": "garbage"})
    assert resp.status_code == 400


def test_hitl_action_unknown_request() -> None:
    client, _, _ = _setup()
    token = TokenSigner("secret").issue(
        request_id="ghost",
        gate=OwnerInteractionKind.CLASSIFICATION,
        decision=OwnerDecision.CONFIRM,
        now=T0,
    )
    resp = client.get("/hitl/action", params={"token": token})
    assert resp.status_code == 404


def test_hitl_action_illegal_for_state() -> None:
    client, service, _ = _setup()
    body = _text_body()
    client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sign(body)})
    service.flush_due(T0 + timedelta(seconds=200))
    token = TokenSigner("secret").issue(
        request_id="req-1",
        gate=OwnerInteractionKind.APPROVAL,
        decision=OwnerDecision.APPROVE,
        now=T0,
    )
    resp = client.get("/hitl/action", params={"token": token})
    assert resp.status_code == 409
