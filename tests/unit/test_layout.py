"""Unit tests for the render-agnostic layout builder (FR-RND-01)."""

from __future__ import annotations

from wapp_planner.documents.branding import Branding
from wapp_planner.documents.content import ExecutionPlanContent, LineItem, Phase, QuoteContent
from wapp_planner.documents.layout import (
    Bullets,
    Heading,
    KeyValues,
    Paragraph,
    Table,
    build_blocks,
)


def _full_quote() -> QuoteContent:
    return QuoteContent(
        title="Bathroom Remodel",
        prepared_for="End Customer",
        scope_summary="Full remodel",
        line_items=[
            LineItem(description="Demo", quantity=2, unit="day", unit_price=400, total=800),
        ],
        subtotal=800,
        tax=None,
        total=800,
        assumptions=["site accessible"],
        exclusions=["permits"],
        validity="30 days",
        notes="thanks",
    )


def _minimal_quote() -> QuoteContent:
    return QuoteContent(
        title="Small Job",
        prepared_for="C",
        scope_summary="x",
        line_items=[LineItem(description="d", quantity=1, unit="ea", unit_price=10, total=10)],
        subtotal=10,
        total=10,
    )


def _block_types(blocks: list[object]) -> list[str]:
    return [type(b).__name__ for b in blocks]


def test_quote_full_blocks_include_all_sections() -> None:
    branding = Branding(company_name="Acme", address="123 St", contact="555", quote_terms="Net 30")
    blocks = build_blocks(_full_quote(), branding)
    # company heading + address + contact present
    assert blocks[0] == Heading("Acme", 1)
    assert Paragraph("123 St") in blocks
    assert Paragraph("555") in blocks
    # the line-items table and money formatting
    table = next(b for b in blocks if isinstance(b, Table))
    assert table.headers[0] == "Description"
    assert table.rows[0] == ["Demo", "2", "day", "$400.00", "$800.00"]
    # tax falls back to TBD
    totals = next(b for b in blocks if isinstance(b, KeyValues) and len(b.pairs) == 3)
    assert ("Tax", "TBD") in totals.pairs
    assert ("Total", "$800.00") in totals.pairs
    assert Bullets("Assumptions", ["site accessible"]) in blocks
    assert Bullets("Exclusions", ["permits"]) in blocks
    assert Paragraph("Validity: 30 days") in blocks
    assert Paragraph("Notes: thanks") in blocks
    assert Paragraph("Net 30") in blocks


def test_quote_minimal_omits_optional_blocks() -> None:
    blocks = build_blocks(_minimal_quote(), Branding())
    # no address/contact/assumptions/exclusions/validity/notes/terms
    assert not any(isinstance(b, Bullets) for b in blocks)
    assert blocks[0] == Heading("[Company Name]", 1)
    assert all(not (isinstance(b, Paragraph) and b.text.startswith("Validity")) for b in blocks)


def test_quote_explicit_tax_used() -> None:
    quote = _minimal_quote().model_copy(update={"tax": "$50.00"})
    blocks = build_blocks(quote, Branding())
    totals = next(b for b in blocks if isinstance(b, KeyValues) and len(b.pairs) == 3)
    assert ("Tax", "$50.00") in totals.pairs


def test_plan_full_blocks() -> None:
    plan = ExecutionPlanContent(
        title="Install Plan",
        overview="overview text",
        materials=["pipe"],
        phases=[
            Phase(
                name="Prep",
                objective="ready",
                steps=["clear", "measure"],
                safety_notes="wear PPE",
                dependencies=["materials on site"],
                estimated_duration="1 day",
            )
        ],
        quality_checkpoints=["level"],
        cleanup="haul debris",
        notes="done",
    )
    blocks = build_blocks(plan, Branding(company_name="Acme"))
    assert Heading("Phase 1: Prep", 2) in blocks
    assert Bullets("Steps", ["clear", "measure"]) in blocks
    assert Paragraph("Safety / code: wear PPE") in blocks
    assert Bullets("Dependencies", ["materials on site"]) in blocks
    assert Paragraph("Estimated duration: 1 day") in blocks
    assert Bullets("Quality checkpoints", ["level"]) in blocks
    assert Paragraph("Cleanup & handover: haul debris") in blocks
    assert Paragraph("Notes: done") in blocks


def test_plan_minimal_omits_optionals() -> None:
    plan = ExecutionPlanContent(
        title="t",
        overview="o",
        phases=[Phase(name="P", objective="obj", steps=["s"])],
    )
    blocks = build_blocks(plan, Branding())
    types = _block_types(blocks)
    # only: company heading, title, overview heading, overview para, phase heading,
    # objective para, steps bullets
    assert "Table" not in types
    assert not any(isinstance(b, Paragraph) and b.text.startswith("Safety") for b in blocks)
    assert not any(isinstance(b, Bullets) and b.title == "Materials & tools" for b in blocks)
