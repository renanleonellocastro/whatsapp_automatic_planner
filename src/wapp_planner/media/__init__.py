"""Media processing: turn raw messages into one normalized transcript (FR-MED-*)."""

from wapp_planner.media.extractors import (
    DocumentTextExtractor,
    FakeDocumentTextExtractor,
    FakeVideoProcessor,
    VideoProcessor,
)
from wapp_planner.media.processor import (
    MediaProcessor,
    NormalizedTranscript,
    TranscriptSegment,
)

__all__ = [
    "DocumentTextExtractor",
    "FakeDocumentTextExtractor",
    "FakeVideoProcessor",
    "VideoProcessor",
    "MediaProcessor",
    "NormalizedTranscript",
    "TranscriptSegment",
]
