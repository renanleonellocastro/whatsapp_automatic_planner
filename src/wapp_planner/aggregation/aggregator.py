"""Group a client's consecutive messages into one request (FR-AGG-01/02/03/04).

A bucket stays *open* while new messages keep arriving within the inactivity
window AND the bucket has not exceeded its maximum total duration. A message
that violates either bound closes the current bucket and starts a new one. Open
buckets can also be flushed by the passage of time (:meth:`Aggregator.flush_due`).

All decisions take an explicit ``now`` (no wall-clock reads), and the open
buckets are plain serializable models so the set survives a restart (FR-AGG-04).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from wapp_planner.domain.models import Message


class OpenBucket(BaseModel):
    """A request being accumulated; exportable for restart-safety (FR-AGG-04)."""

    request_id: str
    client_id: str
    started_at: datetime
    last_at: datetime
    messages: list[Message] = Field(default_factory=list)


class AggregatedRequest(BaseModel):
    """A closed bucket ready to enter the pipeline."""

    request_id: str
    client_id: str
    started_at: datetime
    last_at: datetime
    messages: list[Message]


class Aggregator:
    """Accumulates per-client message buckets and emits them when closed."""

    def __init__(
        self,
        *,
        inactivity_seconds: int,
        max_duration_seconds: int,
        id_factory: Callable[[], str],
    ) -> None:
        self._inactivity = timedelta(seconds=inactivity_seconds)
        self._max_duration = timedelta(seconds=max_duration_seconds)
        self._id_factory = id_factory
        self._open: dict[str, OpenBucket] = {}

    @property
    def open_count(self) -> int:
        return len(self._open)

    def _active(self, bucket: OpenBucket, now: datetime) -> bool:
        """A bucket is active while inside both the inactivity and max windows."""
        return (now - bucket.last_at) < self._inactivity and (
            now - bucket.started_at
        ) < self._max_duration

    def add(self, client_id: str, message: Message, now: datetime) -> AggregatedRequest | None:
        """Add ``message`` to the client's bucket; return any displaced request.

        If the client's open bucket is no longer active, it is closed and
        returned, and ``message`` opens a fresh bucket.
        """
        displaced: AggregatedRequest | None = None
        bucket = self._open.get(client_id)
        if bucket is not None and not self._active(bucket, now):
            displaced = self._emit(client_id)
            bucket = None
        if bucket is None:
            bucket = OpenBucket(
                request_id=self._id_factory(),
                client_id=client_id,
                started_at=now,
                last_at=now,
            )
            self._open[client_id] = bucket
        bucket.messages.append(message.model_copy(update={"order": len(bucket.messages)}))
        bucket.last_at = now
        return displaced

    def flush_due(self, now: datetime) -> list[AggregatedRequest]:
        """Close and return every bucket that is no longer active as of ``now``."""
        due = [cid for cid, bucket in self._open.items() if not self._active(bucket, now)]
        return [self._emit(cid) for cid in due]

    def flush_all(self) -> list[AggregatedRequest]:
        """Close and return every open bucket (e.g. on graceful shutdown)."""
        return [self._emit(cid) for cid in list(self._open)]

    def export_state(self) -> list[OpenBucket]:
        """Snapshot open buckets for persistence (FR-AGG-04)."""
        return list(self._open.values())

    def load_state(self, buckets: list[OpenBucket]) -> None:
        """Restore open buckets after a restart (FR-AGG-04)."""
        self._open = {bucket.client_id: bucket for bucket in buckets}

    def _emit(self, client_id: str) -> AggregatedRequest:
        bucket = self._open.pop(client_id)
        return AggregatedRequest(**bucket.model_dump())
