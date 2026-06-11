"""Build one normalized transcript from a request's messages (FR-MED-06/07).

Each message is converted to one or more labeled, timestamped segments using the
appropriate provider. Failures degrade gracefully: the offending message yields
an ``[unprocessable: <reason>]`` segment and processing continues (FR-MED-07).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from wapp_planner.domain.enums import ProcessingStatus
from wapp_planner.domain.models import Message
from wapp_planner.media.extractors import DocumentTextExtractor, VideoProcessor
from wapp_planner.providers.base import DownloadedMedia, TranscriptionProvider, VisionProvider
from wapp_planner.workflow.enums import MessageType

DEFAULT_VISION_PROMPT = "Describe this construction/renovation photo in detail for a contractor."


class TranscriptSegment(BaseModel):
    """One labeled piece of extracted content (FR-MED-06)."""

    message_id: str
    source: str
    timestamp: datetime
    content: str
    status: ProcessingStatus


class NormalizedTranscript(BaseModel):
    """The ordered, combined transcript for a request (FR-MED-06)."""

    segments: list[TranscriptSegment]

    def render(self) -> str:
        """Render a labeled, timestamped plain-text transcript."""
        return "\n".join(
            f"[{seg.source} @ {seg.timestamp.isoformat()}] {seg.content}" for seg in self.segments
        )

    @property
    def has_content(self) -> bool:
        """True if at least one segment was processed successfully."""
        return any(seg.status is ProcessingStatus.PROCESSED for seg in self.segments)


class MediaProcessor:
    """Converts messages (+ their downloaded media) into a normalized transcript."""

    def __init__(
        self,
        *,
        transcriber: TranscriptionProvider,
        vision: VisionProvider,
        video: VideoProcessor,
        documents: DocumentTextExtractor,
        transcription_model: str,
        vision_model: str,
        vision_prompt: str = DEFAULT_VISION_PROMPT,
        max_video_frames: int = 3,
    ) -> None:
        self._transcriber = transcriber
        self._vision = vision
        self._video = video
        self._documents = documents
        self._transcription_model = transcription_model
        self._vision_model = vision_model
        self._vision_prompt = vision_prompt
        self._max_video_frames = max_video_frames

    def build_transcript(
        self, messages: list[Message], media: dict[str, DownloadedMedia]
    ) -> NormalizedTranscript:
        """Process every message in order into one transcript (FR-MED-06/07)."""
        segments: list[TranscriptSegment] = []
        for msg in sorted(messages, key=lambda m: m.order):
            try:
                segments.extend(self._segments_for(msg, media))
            except Exception as exc:  # noqa: BLE001 - FR-MED-07 graceful degradation
                segments.append(
                    self._segment(
                        msg,
                        msg.type.value,
                        f"[unprocessable: {exc}]",
                        ProcessingStatus.UNPROCESSABLE,
                    )
                )
        return NormalizedTranscript(segments=segments)

    def _segment(
        self,
        msg: Message,
        source: str,
        content: str,
        status: ProcessingStatus = ProcessingStatus.PROCESSED,
    ) -> TranscriptSegment:
        return TranscriptSegment(
            message_id=msg.id,
            source=source,
            timestamp=msg.received_at,
            content=content,
            status=status,
        )

    def _transcribe(self, audio: bytes, mime_type: str | None) -> str:
        return self._transcriber.transcribe(
            audio, model=self._transcription_model, mime_type=mime_type
        ).text

    def _segments_for(
        self, msg: Message, media: dict[str, DownloadedMedia]
    ) -> list[TranscriptSegment]:
        if msg.type is MessageType.TEXT:
            return [self._segment(msg, "text", msg.text or "")]

        downloaded = media.get(msg.id)
        if downloaded is None:
            raise LookupError("no media bytes available")
        content = downloaded.content

        if msg.type in (MessageType.AUDIO, MessageType.VOICE):
            return [self._segment(msg, "audio", self._transcribe(content, downloaded.mime_type))]

        if msg.type is MessageType.IMAGE:
            description = self._vision.describe(
                content,
                model=self._vision_model,
                mime_type=downloaded.mime_type,
                prompt=self._vision_prompt,
            )
            body = f"{msg.caption} — {description}" if msg.caption else description
            return [self._segment(msg, "image", body)]

        if msg.type is MessageType.VIDEO:
            return self._video_segments(msg, content)

        # DOCUMENT
        text = self._documents.extract(content, mime_type=downloaded.mime_type)
        body = f"{msg.filename}: {text}" if msg.filename else text
        return [self._segment(msg, "document", body)]

    def _video_segments(self, msg: Message, content: bytes) -> list[TranscriptSegment]:
        audio = self._video.extract_audio(content)
        segments = [self._segment(msg, "video-audio", self._transcribe(audio, None))]
        for frame in self._video.sample_frames(content, max_frames=self._max_video_frames):
            description = self._vision.describe(
                frame, model=self._vision_model, mime_type="image/jpeg", prompt=self._vision_prompt
            )
            segments.append(self._segment(msg, "video-frame", description))
        return segments
