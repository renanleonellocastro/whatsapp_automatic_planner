"""Unit tests for the idempotency store (NFR-IDEMP-01)."""

from __future__ import annotations

from wapp_planner.ingestion.idempotency import InMemoryIdempotencyStore


def test_first_claim_succeeds_duplicate_fails() -> None:
    store = InMemoryIdempotencyStore()
    assert store.claim("wamid.1") is True
    assert store.claim("wamid.1") is False  # duplicate
    assert store.claim("wamid.2") is True


def test_seen_reflects_claims() -> None:
    store = InMemoryIdempotencyStore()
    assert not store.seen("k")
    store.claim("k")
    assert store.seen("k")
