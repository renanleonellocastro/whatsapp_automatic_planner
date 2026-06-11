"""Unit tests for media extractor fakes."""

from __future__ import annotations

from wapp_planner.media.extractors import FakeDocumentTextExtractor, FakeVideoProcessor


def test_fake_video_processor_defaults() -> None:
    video = FakeVideoProcessor()
    assert video.extract_audio(b"v") == b"audio"
    assert video.sample_frames(b"v", max_frames=5) == [b"frame-0"]


def test_fake_video_processor_respects_max_frames() -> None:
    video = FakeVideoProcessor(audio=b"a", frames=[b"f0", b"f1", b"f2"])
    assert video.extract_audio(b"v") == b"a"
    assert video.sample_frames(b"v", max_frames=2) == [b"f0", b"f1"]


def test_fake_document_extractor() -> None:
    docs = FakeDocumentTextExtractor(text="scope of work")
    assert docs.extract(b"%PDF", mime_type="application/pdf") == "scope of work"
