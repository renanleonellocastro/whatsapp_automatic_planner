"""Real media extractors: ffmpeg video + simple document text (FR-MED-02/04).

:class:`SubprocessVideoProcessor` pipes bytes through an injected command runner
(so it is unit-tested with a fake runner — no ffmpeg needed). Use
:func:`subprocess_runner` in production. :class:`SimpleDocumentTextExtractor`
decodes ``text/*`` attachments; other types raise (the media pipeline then marks
the segment unprocessable, FR-MED-07).
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable

from wapp_planner.media.extractors import DocumentTextExtractor, VideoProcessor

#: A command runner: takes argv and stdin bytes, returns stdout bytes.
CommandRunner = Callable[[list[str], bytes], bytes]


class SubprocessVideoProcessor(VideoProcessor):
    """Extracts audio and frames from video by piping through ffmpeg."""

    def __init__(self, run: CommandRunner, *, audio_format: str = "mp3") -> None:
        self._run = run
        self._audio_format = audio_format

    def extract_audio(self, video: bytes) -> bytes:
        return self._run(
            ["ffmpeg", "-hide_banner", "-i", "pipe:0", "-vn", "-f", self._audio_format, "pipe:1"],
            video,
        )

    def sample_frames(self, video: bytes, *, max_frames: int) -> list[bytes]:
        frames: list[bytes] = []
        for index in range(max_frames):
            frames.append(
                self._run(
                    [
                        "ffmpeg",
                        "-hide_banner",
                        "-i",
                        "pipe:0",
                        "-vf",
                        f"select=eq(n\\,{index})",
                        "-frames:v",
                        "1",
                        "-f",
                        "image2",
                        "pipe:1",
                    ],
                    video,
                )
            )
        return frames


class SimpleDocumentTextExtractor(DocumentTextExtractor):
    """Decodes text attachments; rejects binary types it cannot read."""

    def extract(self, data: bytes, *, mime_type: str) -> str:
        if mime_type.startswith("text/"):
            return data.decode("utf-8", errors="replace")
        raise ValueError(f"unsupported document type: {mime_type!r}")


def subprocess_runner(
    *, timeout: float = 60.0
) -> CommandRunner:  # pragma: no cover - spawns ffmpeg
    """Return a CommandRunner that shells out via ``subprocess.run``."""

    def _run(argv: list[str], stdin: bytes) -> bytes:
        completed = subprocess.run(
            argv, input=stdin, capture_output=True, timeout=timeout, check=True
        )
        return completed.stdout

    return _run
