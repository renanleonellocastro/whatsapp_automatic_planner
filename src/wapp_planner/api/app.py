"""FastAPI application wiring the HTTP surface to the services (DEP-02/04).

Endpoints:

* ``GET  /webhook``      — Meta subscription verification handshake (FR-ING-02).
* ``POST /webhook``      — inbound messages; signature-checked, then ingested.
* ``GET  /hitl/action``  — a clicked owner action link; resolves + applies it.
* ``GET  /health``       — liveness.

The handlers stay thin: all logic lives in the services. ``now`` is injected so
tests can pin time.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse

from wapp_planner import clock
from wapp_planner.hitl.service import NotificationService
from wapp_planner.hitl.tokens import TokenError
from wapp_planner.ingestion.service import IngestionService, InvalidPayloadError, SignatureError
from wapp_planner.ingestion.signature import WebhookVerificationError
from wapp_planner.orchestrator.orchestrator import Orchestrator, UnknownRequestError
from wapp_planner.workflow.state_machine import IllegalTransitionError

SIGNATURE_HEADER = "X-Hub-Signature-256"


@dataclass
class AppContext:
    """The services the HTTP layer delegates to."""

    ingestion: IngestionService
    notifications: NotificationService
    orchestrator: Orchestrator
    now: Callable[[], datetime] = field(default=clock.now)


def create_app(ctx: AppContext) -> FastAPI:
    """Build the FastAPI app bound to ``ctx``."""
    app = FastAPI(title="WhatsApp Service Planner")
    app.state.context = ctx  # so the entrypoint can reach the ingestion service

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/webhook")
    def verify(
        mode: str | None = Query(default=None, alias="hub.mode"),
        token: str | None = Query(default=None, alias="hub.verify_token"),
        challenge: str = Query(default="", alias="hub.challenge"),
    ) -> Response:
        try:
            return PlainTextResponse(ctx.ingestion.verify_subscription(mode, token, challenge))
        except WebhookVerificationError as exc:
            raise HTTPException(status_code=403, detail="verification failed") from exc

    @app.post("/webhook")
    async def inbound(request: Request) -> dict[str, int]:
        body = await request.body()
        signature = request.headers.get(SIGNATURE_HEADER)
        try:
            accepted = ctx.ingestion.receive(body, signature, now=ctx.now())
        except SignatureError as exc:
            raise HTTPException(status_code=403, detail="invalid signature") from exc
        except InvalidPayloadError as exc:
            raise HTTPException(status_code=400, detail="invalid payload") from exc
        return {"accepted": accepted}

    @app.get("/hitl/action")
    def hitl_action(
        token: str = Query(...),
        feedback: str | None = Query(default=None),
    ) -> dict[str, str]:
        try:
            action = ctx.notifications.resolve_action(token, now=ctx.now(), feedback=feedback)
        except TokenError as exc:
            raise HTTPException(status_code=400, detail="invalid or expired link") from exc
        try:
            request = ctx.orchestrator.apply_owner_action(action, now=ctx.now())
        except UnknownRequestError as exc:
            raise HTTPException(status_code=404, detail="request not found") from exc
        except IllegalTransitionError as exc:
            raise HTTPException(status_code=409, detail="action not allowed now") from exc
        return {"request_id": request.id, "state": request.state.value}

    return app
