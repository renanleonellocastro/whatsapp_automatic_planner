"""In-memory fakes for every provider interface (TST-08).

These let the full pipeline run deterministically in tests and in the local
end-to-end harness with no real WhatsApp/OpenAI/AWS/SMTP. Each fake records its
calls for assertions and supports simple scripted responses and failure
injection (TST-06).
"""

from __future__ import annotations

from typing import Any

from wapp_planner.domain.enums import Channel
from wapp_planner.providers.base import (
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


class FakeLLMProvider(LLMProvider):
    """Returns scripted completions; falls back to a default. Records calls."""

    def __init__(
        self,
        *,
        default_text: str = "",
        responses: list[LLMResult] | None = None,
        cost_per_call: float = 0.0,
    ) -> None:
        self.default_text = default_text
        self.responses = list(responses or [])
        self.cost_per_call = cost_per_call
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResult:
        self.calls.append(
            {
                "system": system,
                "user": user,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self.responses:
            return self.responses.pop(0)
        return LLMResult(text=self.default_text, model=model, cost_usd=self.cost_per_call)


class FakeTranscriptionProvider(TranscriptionProvider):
    """Returns scripted transcripts; falls back to a default. Records calls."""

    def __init__(
        self,
        *,
        default_text: str = "",
        results: list[TranscriptionResult] | None = None,
    ) -> None:
        self.default_text = default_text
        self.results = list(results or [])
        self.calls: list[dict[str, Any]] = []

    def transcribe(
        self, audio: bytes, *, model: str, mime_type: str | None = None
    ) -> TranscriptionResult:
        self.calls.append({"size": len(audio), "model": model, "mime_type": mime_type})
        if self.results:
            return self.results.pop(0)
        return TranscriptionResult(text=self.default_text, model=model)


class FakeVisionProvider(VisionProvider):
    """Returns scripted image descriptions; falls back to a default."""

    def __init__(self, *, default: str = "", descriptions: list[str] | None = None) -> None:
        self.default = default
        self.descriptions = list(descriptions or [])
        self.calls: list[dict[str, Any]] = []

    def describe(self, image: bytes, *, model: str, mime_type: str, prompt: str) -> str:
        self.calls.append(
            {"size": len(image), "model": model, "mime_type": mime_type, "prompt": prompt}
        )
        if self.descriptions:
            return self.descriptions.pop(0)
        return self.default


class InMemoryStorage(StorageProvider):
    """Dict-backed object store. Reference is ``memory://<key>``."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, data: bytes, *, content_type: str) -> str:
        self._store[key] = (data, content_type)
        return f"memory://{key}"

    def get(self, key: str) -> bytes:
        if key not in self._store:
            raise KeyError(key)
        return self._store[key][0]

    def content_type(self, key: str) -> str:
        if key not in self._store:
            raise KeyError(key)
        return self._store[key][1]

    def exists(self, key: str) -> bool:
        return key in self._store

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class RecordingNotifier(Notifier):
    """Records every sent message; can inject a send failure (TST-06)."""

    def __init__(self, channel: Channel, *, raise_on_send: Exception | None = None) -> None:
        self.channel = channel
        self.raise_on_send = raise_on_send
        self.sent: list[OutboundMessage] = []
        self._counter = 0

    def send(self, message: OutboundMessage) -> str:
        if self.raise_on_send is not None:
            raise self.raise_on_send
        self.sent.append(message)
        self._counter += 1
        return f"{self.channel.value}-msg-{self._counter}"


class FakeWhatsAppMediaClient(WhatsAppMediaClient):
    """Serves preloaded media bytes by id; unknown ids raise KeyError."""

    def __init__(self, media: dict[str, DownloadedMedia] | None = None) -> None:
        self._media: dict[str, DownloadedMedia] = dict(media or {})

    def add(self, media_id: str, content: bytes, mime_type: str) -> None:
        self._media[media_id] = DownloadedMedia(content=content, mime_type=mime_type)

    def download(self, media_id: str) -> DownloadedMedia:
        if media_id not in self._media:
            raise KeyError(media_id)
        return self._media[media_id]
