"""Idempotency primitive for at-least-once inbound delivery (NFR-IDEMP-01).

WhatsApp webhook delivery (and owner responses) can arrive more than once. A
:class:`IdempotencyStore` lets a caller atomically *claim* a key the first time
it is seen so duplicates are processed exactly once.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IdempotencyStore(ABC):
    """Tracks which keys have already been processed."""

    @abstractmethod
    def claim(self, key: str) -> bool:
        """Mark ``key`` seen and return ``True`` if this is the first claim.

        Returns ``False`` if ``key`` was already claimed (a duplicate).
        """
        raise NotImplementedError

    @abstractmethod
    def seen(self, key: str) -> bool:
        raise NotImplementedError


class InMemoryIdempotencyStore(IdempotencyStore):
    """Process-local set-backed store (suitable for a single worker / tests)."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def claim(self, key: str) -> bool:
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

    def seen(self, key: str) -> bool:
        return key in self._seen
