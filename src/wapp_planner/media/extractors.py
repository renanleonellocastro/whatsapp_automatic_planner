"""Interfaces (and fakes) for video and document extraction (FR-MED-02/04).

Real implementations shell out to ffmpeg (audio track + key frames) and a PDF
text extractor; those are wired at deployment. The interfaces keep the media
pipeline testable without those binaries.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class VideoProcessor(ABC):
    """Extracts the audio track and representative frames from a video."""

    @abstractmethod
    def extract_audio(self, video: bytes) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def sample_frames(self, video: bytes, *, max_frames: int) -> list[bytes]:
        raise NotImplementedError


class DocumentTextExtractor(ABC):
    """Extracts text from a document attachment (e.g. PDF)."""

    @abstractmethod
    def extract(self, data: bytes, *, mime_type: str) -> str:
        raise NotImplementedError


class FakeVideoProcessor(VideoProcessor):
    """Returns scripted audio bytes and frames for tests."""

    def __init__(self, *, audio: bytes = b"audio", frames: list[bytes] | None = None) -> None:
        self._audio = audio
        self._frames = list(frames if frames is not None else [b"frame-0"])

    def extract_audio(self, video: bytes) -> bytes:
        return self._audio

    def sample_frames(self, video: bytes, *, max_frames: int) -> list[bytes]:
        return self._frames[:max_frames]


class FakeDocumentTextExtractor(DocumentTextExtractor):
    """Returns a scripted document text for tests."""

    def __init__(self, *, text: str = "document text") -> None:
        self._text = text

    def extract(self, data: bytes, *, mime_type: str) -> str:
        return self._text
