"""Unit tests for the client registry (FR-CFG-01, FR-ING-08)."""

from __future__ import annotations

from wapp_planner.domain.models import Client
from wapp_planner.ingestion.client_registry import ClientRegistry


def _registry() -> ClientRegistry:
    return ClientRegistry(
        [Client(id="c1", name="Bob Builder", phone_numbers=["15551230000", "15559999999"])]
    )


def test_resolve_known_client_by_either_number() -> None:
    reg = _registry()
    assert reg.resolve("15551230000") == ("c1", "Bob Builder", True)
    assert reg.resolve("15559999999") == ("c1", "Bob Builder", True)


def test_resolve_unknown_uses_phone_as_id_and_name() -> None:
    assert _registry().resolve("14040000000") == ("14040000000", "14040000000", False)


def test_name_for_known_and_unknown() -> None:
    reg = _registry()
    assert reg.name_for("c1") == "Bob Builder"
    assert reg.name_for("ghost") == "ghost"
