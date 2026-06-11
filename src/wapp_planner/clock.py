"""Time source.

A single indirection over the wall clock so the rest of the system never calls
``datetime.now`` directly. Tests inject fixed timestamps; production uses
:func:`now`. Keeping this isolated also keeps domain models deterministic.
"""

from __future__ import annotations

from datetime import UTC, datetime


def now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""

    return datetime.now(UTC)
