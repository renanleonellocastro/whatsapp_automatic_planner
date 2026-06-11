"""Unit tests for structured document content models (§11)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from wapp_planner.documents.content import ExecutionPlanContent, LineItem, Phase, QuoteContent


def test_line_item_rejects_negatives() -> None:
    with pytest.raises(ValidationError):
        LineItem(description="x", quantity=-1, unit="ea", unit_price=1, total=1)


def test_quote_content_defaults() -> None:
    quote = QuoteContent(
        title="t",
        prepared_for="c",
        scope_summary="s",
        line_items=[LineItem(description="d", quantity=1, unit="job", unit_price=10, total=10)],
        subtotal=10,
        total=10,
    )
    assert quote.tax is None
    assert quote.assumptions == []


def test_execution_plan_requires_phase_steps() -> None:
    with pytest.raises(ValidationError):
        Phase(name="p", objective="o")  # type: ignore[call-arg]
    plan = ExecutionPlanContent(
        title="t",
        overview="o",
        phases=[Phase(name="Prep", objective="ready", steps=["clear"])],
    )
    assert plan.materials == []
    assert plan.phases[0].steps == ["clear"]
