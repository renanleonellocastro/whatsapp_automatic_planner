"""External-service provider interfaces and in-memory fakes (NFR-PORT-01).

Every outbound dependency (LLM, transcription, vision, object storage,
notifications, WhatsApp media) sits behind an interface here so providers can be
swapped (e.g. OpenAI -> Anthropic) and so the whole flow runs against fakes in
tests with no real services (TST-08).
"""

from wapp_planner.providers.base import (
    Attachment,
    DownloadedMedia,
    LLMProvider,
    LLMResult,
    Notifier,
    OutboundMessage,
    StorageProvider,
    TranscriptionProvider,
    TranscriptionResult,
    VisionProvider,
    WhatsAppMediaClient,
)

__all__ = [
    "Attachment",
    "DownloadedMedia",
    "LLMProvider",
    "LLMResult",
    "Notifier",
    "OutboundMessage",
    "StorageProvider",
    "TranscriptionProvider",
    "TranscriptionResult",
    "VisionProvider",
    "WhatsAppMediaClient",
]
