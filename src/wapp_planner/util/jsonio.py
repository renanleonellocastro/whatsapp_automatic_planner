"""Extract a JSON object embedded in free-form LLM text.

Models sometimes wrap their JSON in prose or code fences. This pulls out the
substring from the first ``{`` to the last ``}`` so it can be parsed.
"""

from __future__ import annotations


def extract_json_object(text: str) -> str:
    """Return the ``{...}`` substring of ``text``; raise ``ValueError`` if absent."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in text")
    return text[start : end + 1]
