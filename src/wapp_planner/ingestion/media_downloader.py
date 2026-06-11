"""Download inbound WhatsApp media and persist it to storage (FR-ING-07).

Enforces the media safety bounds (NFR-SEC-02): a maximum byte size and an
allowed-MIME-prefix allowlist are checked *before* the bytes are stored.
"""

from __future__ import annotations

from pydantic import BaseModel

from wapp_planner.providers.base import StorageProvider, WhatsAppMediaClient

#: MIME prefixes we accept for inbound media (NFR-SEC-02).
DEFAULT_ALLOWED_MIME_PREFIXES: tuple[str, ...] = (
    "audio/",
    "video/",
    "image/",
    "application/pdf",
    "text/",
)


class MediaTooLargeError(Exception):
    """Raised when a media payload exceeds the configured size cap."""


class MediaRejectedError(Exception):
    """Raised when a media payload has a disallowed MIME type."""


class StoredMedia(BaseModel):
    """Reference to media that has been downloaded and stored."""

    key: str
    ref: str
    mime_type: str
    size: int


class MediaDownloader:
    """Fetches media via the Graph API client and stores it in object storage."""

    def __init__(
        self,
        client: WhatsAppMediaClient,
        storage: StorageProvider,
        *,
        max_bytes: int,
        allowed_mime_prefixes: tuple[str, ...] = DEFAULT_ALLOWED_MIME_PREFIXES,
    ) -> None:
        self._client = client
        self._storage = storage
        self._max_bytes = max_bytes
        self._allowed = allowed_mime_prefixes

    def _check_mime(self, mime_type: str) -> None:
        if not any(mime_type.startswith(prefix) for prefix in self._allowed):
            raise MediaRejectedError(f"disallowed media type: {mime_type!r}")

    def fetch_and_store(self, *, request_id: str, message_id: str, media_id: str) -> StoredMedia:
        """Download ``media_id``, validate it, store it, and return a reference."""
        media = self._client.download(media_id)
        self._check_mime(media.mime_type)
        if media.size > self._max_bytes:
            raise MediaTooLargeError(f"media {media.size} bytes exceeds cap {self._max_bytes}")
        key = f"{request_id}/{message_id}"
        ref = self._storage.put(key, media.content, content_type=media.mime_type)
        return StoredMedia(key=key, ref=ref, mime_type=media.mime_type, size=media.size)
