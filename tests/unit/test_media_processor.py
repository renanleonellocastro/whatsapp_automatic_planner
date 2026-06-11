"""Unit tests for the media processing pipeline (FR-MED-06/07)."""

from __future__ import annotations

from datetime import UTC, datetime

from wapp_planner.domain.enums import ProcessingStatus
from wapp_planner.domain.models import Message
from wapp_planner.media.extractors import (
    FakeDocumentTextExtractor,
    FakeVideoProcessor,
    VideoProcessor,
)
from wapp_planner.media.processor import MediaProcessor, NormalizedTranscript, TranscriptSegment
from wapp_planner.providers.base import DownloadedMedia, TranscriptionResult, VisionProvider
from wapp_planner.providers.fakes import FakeTranscriptionProvider, FakeVisionProvider
from wapp_planner.workflow.enums import MessageType

TS = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)


def _processor(**overrides: object) -> MediaProcessor:
    kwargs: dict[str, object] = {
        "transcriber": FakeTranscriptionProvider(default_text="spoken words"),
        "vision": FakeVisionProvider(default="a tiled wall"),
        "video": FakeVideoProcessor(frames=[b"f0", b"f1"]),
        "documents": FakeDocumentTextExtractor(text="doc body"),
        "transcription_model": "w",
        "vision_model": "v",
        "max_video_frames": 2,
    }
    kwargs.update(overrides)
    return MediaProcessor(**kwargs)  # type: ignore[arg-type]


def _msg(mtype: MessageType, *, order: int = 0, mid: str = "m", **kw: object) -> Message:
    return Message(id=mid, type=mtype, order=order, received_at=TS, **kw)  # type: ignore[arg-type]


def test_text_message_segment() -> None:
    t = _processor().build_transcript([_msg(MessageType.TEXT, text="need a quote")], {})
    assert t.segments[0].source == "text"
    assert t.segments[0].content == "need a quote"
    assert t.segments[0].status is ProcessingStatus.PROCESSED


def test_text_message_with_no_body() -> None:
    t = _processor().build_transcript([_msg(MessageType.TEXT)], {})
    assert t.segments[0].content == ""


def test_audio_and_voice_transcribed() -> None:
    media = {"a": DownloadedMedia(content=b"x", mime_type="audio/ogg")}
    for mtype in (MessageType.AUDIO, MessageType.VOICE):
        t = _processor().build_transcript([_msg(mtype, mid="a")], media)
        assert t.segments[0].source == "audio"
        assert t.segments[0].content == "spoken words"


def test_image_with_caption() -> None:
    media = {"i": DownloadedMedia(content=b"x", mime_type="image/jpeg")}
    t = _processor().build_transcript(
        [_msg(MessageType.IMAGE, mid="i", caption="north wall")], media
    )
    assert t.segments[0].content == "north wall — a tiled wall"


def test_image_without_caption() -> None:
    media = {"i": DownloadedMedia(content=b"x", mime_type="image/jpeg")}
    t = _processor().build_transcript([_msg(MessageType.IMAGE, mid="i")], media)
    assert t.segments[0].content == "a tiled wall"


def test_video_yields_audio_then_frames() -> None:
    media = {"v": DownloadedMedia(content=b"x", mime_type="video/mp4")}
    t = _processor().build_transcript([_msg(MessageType.VIDEO, mid="v")], media)
    sources = [s.source for s in t.segments]
    assert sources == ["video-audio", "video-frame", "video-frame"]
    assert t.segments[0].content == "spoken words"


def test_document_with_filename() -> None:
    media = {"d": DownloadedMedia(content=b"x", mime_type="application/pdf")}
    t = _processor().build_transcript(
        [_msg(MessageType.DOCUMENT, mid="d", filename="scope.pdf")], media
    )
    assert t.segments[0].content == "scope.pdf: doc body"


def test_document_without_filename() -> None:
    media = {"d": DownloadedMedia(content=b"x", mime_type="application/pdf")}
    t = _processor().build_transcript([_msg(MessageType.DOCUMENT, mid="d")], media)
    assert t.segments[0].content == "doc body"


def test_missing_media_bytes_is_unprocessable() -> None:
    t = _processor().build_transcript([_msg(MessageType.AUDIO, mid="a")], {})
    seg = t.segments[0]
    assert seg.status is ProcessingStatus.UNPROCESSABLE
    assert "no media bytes available" in seg.content


def test_provider_failure_degrades_gracefully() -> None:
    class BoomVision(VisionProvider):
        def describe(self, image: bytes, *, model: str, mime_type: str, prompt: str) -> str:
            raise RuntimeError("vision down")

    media = {"i": DownloadedMedia(content=b"x", mime_type="image/jpeg")}
    t = _processor(vision=BoomVision()).build_transcript([_msg(MessageType.IMAGE, mid="i")], media)
    seg = t.segments[0]
    assert seg.status is ProcessingStatus.UNPROCESSABLE
    assert seg.content == "[unprocessable: vision down]"
    assert not t.has_content  # FR-MED-07: nothing processed


def test_one_bad_message_does_not_stop_the_rest() -> None:
    class BoomVideo(VideoProcessor):
        def extract_audio(self, video: bytes) -> bytes:
            raise RuntimeError("ffmpeg missing")

        def sample_frames(self, video: bytes, *, max_frames: int) -> list[bytes]:
            raise RuntimeError("ffmpeg missing")  # pragma: no cover - not reached

    media = {"v": DownloadedMedia(content=b"x", mime_type="video/mp4")}
    messages = [
        _msg(MessageType.TEXT, order=0, mid="t", text="hello"),
        _msg(MessageType.VIDEO, order=1, mid="v"),
    ]
    t = _processor(video=BoomVideo()).build_transcript(media=media, messages=messages)
    assert t.segments[0].content == "hello"
    assert t.segments[1].status is ProcessingStatus.UNPROCESSABLE
    assert t.has_content  # the text segment succeeded


def test_messages_processed_in_order_regardless_of_input_order() -> None:
    messages = [
        _msg(MessageType.TEXT, order=2, mid="c", text="third"),
        _msg(MessageType.TEXT, order=0, mid="a", text="first"),
        _msg(MessageType.TEXT, order=1, mid="b", text="second"),
    ]
    t = _processor().build_transcript(messages, {})
    assert [s.content for s in t.segments] == ["first", "second", "third"]


def test_render_is_labeled_and_timestamped() -> None:
    transcript = NormalizedTranscript(
        segments=[
            TranscriptSegment(
                message_id="m",
                source="text",
                timestamp=TS,
                content="hi",
                status=ProcessingStatus.PROCESSED,
            )
        ]
    )
    rendered = transcript.render()
    assert rendered == "[text @ 2026-06-11T12:00:00+00:00] hi"


def test_scripted_transcription_result_used() -> None:
    transcriber = FakeTranscriptionProvider(results=[TranscriptionResult(text="custom", model="w")])
    media = {"a": DownloadedMedia(content=b"x", mime_type="audio/ogg")}
    t = _processor(transcriber=transcriber).build_transcript(
        [_msg(MessageType.AUDIO, mid="a")], media
    )
    assert t.segments[0].content == "custom"
