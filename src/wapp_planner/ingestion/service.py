"""Inbound ingestion service — webhook to aggregated processing (FR-ING-*).

Validates the webhook signature, parses the payload, dedupes by message id,
downloads media, and feeds each message into the aggregator. Closed buckets
(displaced by a new message, or flushed by elapsed time) are handed to the
orchestrator with their media reloaded from storage.
"""

from __future__ import annotations

import json
from datetime import datetime

from wapp_planner.aggregation.aggregator import AggregatedRequest, Aggregator
from wapp_planner.domain.models import Message
from wapp_planner.ingestion.client_registry import ClientRegistry
from wapp_planner.ingestion.idempotency import IdempotencyStore
from wapp_planner.ingestion.media_downloader import MediaDownloader
from wapp_planner.ingestion.parser import ParsedMessage, parse_webhook
from wapp_planner.ingestion.signature import is_valid_signature, verify_subscription
from wapp_planner.orchestrator.orchestrator import Orchestrator
from wapp_planner.providers.base import DownloadedMedia, StorageProvider

UNKNOWN_CLIENT_FLAG = "unknown_client"
_DEFAULT_MIME = "application/octet-stream"


class SignatureError(Exception):
    """Raised when an inbound webhook signature is invalid (FR-ING-03)."""


class InvalidPayloadError(Exception):
    """Raised when a (signed) webhook body is not valid JSON."""


class IngestionService:
    """Turns inbound webhooks into processed, aggregated requests."""

    def __init__(
        self,
        *,
        app_secret: str,
        verify_token: str,
        idempotency: IdempotencyStore,
        media_downloader: MediaDownloader,
        storage: StorageProvider,
        aggregator: Aggregator,
        orchestrator: Orchestrator,
        registry: ClientRegistry,
    ) -> None:
        self._app_secret = app_secret
        self._verify_token = verify_token
        self._idempotency = idempotency
        self._downloader = media_downloader
        self._storage = storage
        self._aggregator = aggregator
        self._orchestrator = orchestrator
        self._registry = registry
        self._names: dict[str, str] = {}
        self._known: dict[str, bool] = {}

    def verify_subscription(self, mode: str | None, token: str | None, challenge: str) -> str:
        """Handle the GET verification handshake (FR-ING-02)."""
        return verify_subscription(mode, token, challenge, expected_token=self._verify_token)

    def receive(self, raw_body: bytes, signature_header: str | None, *, now: datetime) -> int:
        """Validate, parse and ingest a webhook body; return accepted message count."""
        if not is_valid_signature(raw_body, signature_header, app_secret=self._app_secret):
            raise SignatureError("invalid webhook signature")
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise InvalidPayloadError(str(exc)) from exc

        accepted = 0
        for parsed in parse_webhook(payload).messages:
            if not self._idempotency.claim(parsed.whatsapp_id):
                continue  # duplicate delivery (NFR-IDEMP-01)
            accepted += 1
            client_id, client_name, known = self._registry.resolve(parsed.sender)
            self._names[client_id] = client_name
            self._known[client_id] = known
            message = self._build_message(parsed)
            displaced = self._aggregator.add(client_id, message, now)
            if displaced is not None:
                self._process(displaced, now)
        return accepted

    def flush_due(self, now: datetime) -> int:
        """Process buckets whose window has closed; return count processed."""
        due = self._aggregator.flush_due(now)
        for aggregated in due:
            self._process(aggregated, now)
        return len(due)

    def _build_message(self, parsed: ParsedMessage) -> Message:
        raw_ref: str | None = None
        if parsed.type is not None and parsed.media_id is not None and parsed.type.value != "text":
            try:
                stored = self._downloader.fetch_and_store(
                    request_id="inbound", message_id=parsed.whatsapp_id, media_id=parsed.media_id
                )
                raw_ref = stored.key
            except Exception:  # noqa: BLE001 - FR-MED-07: keep going; segment marked later
                raw_ref = None
        return Message(
            id=parsed.whatsapp_id,
            type=parsed.type,
            order=0,
            received_at=parsed.timestamp,
            text=parsed.text,
            caption=parsed.caption,
            media_id=parsed.media_id,
            mime_type=parsed.mime_type,
            filename=parsed.filename,
            raw_ref=raw_ref,
        )

    def _media_for(self, messages: list[Message]) -> dict[str, DownloadedMedia]:
        media: dict[str, DownloadedMedia] = {}
        for message in messages:
            if message.is_media and message.raw_ref is not None:
                media[message.id] = DownloadedMedia(
                    content=self._storage.get(message.raw_ref),
                    mime_type=message.mime_type or _DEFAULT_MIME,
                )
        return media

    def _process(self, aggregated: AggregatedRequest, now: datetime) -> None:
        media = self._media_for(aggregated.messages)
        client_id = aggregated.client_id
        extra_flags = [] if self._known.get(client_id, True) else [UNKNOWN_CLIENT_FLAG]
        self._orchestrator.ingest(
            aggregated,
            media,
            client_name=self._names.get(client_id, client_id),
            now=now,
            extra_flags=extra_flags,
        )
