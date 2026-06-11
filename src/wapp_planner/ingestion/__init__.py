"""Inbound ingestion: webhook verification, payload parsing, idempotency, media.

Implements REQUIREMENTS FR-ING-*, NFR-IDEMP-01 and NFR-SEC-02.
"""

from wapp_planner.ingestion.client_registry import ClientRegistry
from wapp_planner.ingestion.idempotency import IdempotencyStore, InMemoryIdempotencyStore
from wapp_planner.ingestion.media_downloader import (
    MediaDownloader,
    MediaRejectedError,
    MediaTooLargeError,
    StoredMedia,
)
from wapp_planner.ingestion.parser import ParsedMessage, ParseResult, parse_webhook
from wapp_planner.ingestion.service import (
    IngestionService,
    InvalidPayloadError,
    SignatureError,
)
from wapp_planner.ingestion.signature import (
    WebhookVerificationError,
    is_valid_signature,
    verify_subscription,
)

__all__ = [
    "ClientRegistry",
    "IngestionService",
    "InvalidPayloadError",
    "SignatureError",
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "MediaDownloader",
    "MediaRejectedError",
    "MediaTooLargeError",
    "StoredMedia",
    "ParsedMessage",
    "ParseResult",
    "parse_webhook",
    "WebhookVerificationError",
    "is_valid_signature",
    "verify_subscription",
]
