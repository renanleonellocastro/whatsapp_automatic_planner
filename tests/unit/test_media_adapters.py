"""Unit tests for the real media adapters (FR-MED-02/04)."""

from __future__ import annotations

import pytest

from wapp_planner.media.adapters import SimpleDocumentTextExtractor, SubprocessVideoProcessor


def test_video_extract_audio_invokes_ffmpeg_pipe() -> None:
    calls: list[list[str]] = []

    def run(argv: list[str], stdin: bytes) -> bytes:
        calls.append(argv)
        return b"audio-out"

    processor = SubprocessVideoProcessor(run)
    assert processor.extract_audio(b"video") == b"audio-out"
    assert "pipe:0" in calls[0]
    assert "-vn" in calls[0]


def test_video_sample_frames_runs_once_per_frame() -> None:
    outputs = [b"f0", b"f1", b"f2"]
    seen_args: list[list[str]] = []

    def run(argv: list[str], stdin: bytes) -> bytes:
        seen_args.append(argv)
        return outputs.pop(0)

    processor = SubprocessVideoProcessor(run)
    frames = processor.sample_frames(b"video", max_frames=2)
    assert frames == [b"f0", b"f1"]
    assert len(seen_args) == 2
    assert "select=eq(n\\,0)" in seen_args[0]


def test_document_extractor_decodes_text() -> None:
    extractor = SimpleDocumentTextExtractor()
    assert extractor.extract(b"scope of work", mime_type="text/plain") == "scope of work"


def test_document_extractor_rejects_binary() -> None:
    with pytest.raises(ValueError, match="unsupported document type"):
        SimpleDocumentTextExtractor().extract(b"%PDF", mime_type="application/pdf")
