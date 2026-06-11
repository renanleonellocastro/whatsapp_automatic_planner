"""Provider interfaces and their data-transfer models (NFR-PORT-01).

Interfaces are ABCs with abstract methods; concrete implementations live in
sibling modules (fakes here, real OpenAI/S3/SMTP/Graph adapters added per phase).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field

from wapp_planner.domain.enums import Channel


# ── Data-transfer models ────────────────────────────────────────────────
class LLMResult(BaseModel):
    """Outcome of an LLM completion, with usage for cost tracking (NFR-COST-01)."""

    text: str
    model: str
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)


class TranscriptionResult(BaseModel):
    """Outcome of a speech-to-text transcription (FR-MED-01)."""

    text: str
    model: str
    language: str | None = None
    cost_usd: float = Field(default=0.0, ge=0.0)


class DownloadedMedia(BaseModel):
    """Bytes downloaded from WhatsApp for a media message (FR-ING-07)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    content: bytes
    mime_type: str

    @property
    def size(self) -> int:
        return len(self.content)


class Attachment(BaseModel):
    """A file attached to an outbound owner message (FR-DLV-01)."""

    filename: str
    content: bytes
    content_type: str


class OutboundMessage(BaseModel):
    """A message the system sends to the owner (notification or delivery)."""

    recipient: str
    body: str
    subject: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)


# ── Interfaces ──────────────────────────────────────────────────────────
class LLMProvider(ABC):
    """Text completion used for classification and document generation (AD-2)."""

    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResult:
        raise NotImplementedError


class TranscriptionProvider(ABC):
    """Speech-to-text for audio/voice and video audio tracks (FR-MED-01/02)."""

    @abstractmethod
    def transcribe(
        self, audio: bytes, *, model: str, mime_type: str | None = None
    ) -> TranscriptionResult:
        raise NotImplementedError


class VisionProvider(ABC):
    """Image/video-frame description (FR-MED-02/03)."""

    @abstractmethod
    def describe(self, image: bytes, *, model: str, mime_type: str, prompt: str) -> str:
        raise NotImplementedError


class StorageProvider(ABC):
    """Object storage for media and rendered artifacts (FR-ING-07, FR-RND-03)."""

    @abstractmethod
    def put(self, key: str, data: bytes, *, content_type: str) -> str:
        """Store ``data`` under ``key`` and return a stable reference."""
        raise NotImplementedError

    @abstractmethod
    def get(self, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def exists(self, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError


class Notifier(ABC):
    """Sends an owner-facing message over one concrete channel (AD-3)."""

    #: The concrete channel this notifier serves.
    channel: Channel

    @abstractmethod
    def send(self, message: OutboundMessage) -> str:
        """Send ``message`` and return a provider message id."""
        raise NotImplementedError


class WhatsAppMediaClient(ABC):
    """Downloads inbound WhatsApp media via the Graph API (FR-ING-07)."""

    @abstractmethod
    def download(self, media_id: str) -> DownloadedMedia:
        raise NotImplementedError
