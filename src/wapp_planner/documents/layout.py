"""Render-agnostic document layout: structured content -> ordered blocks.

This is where all the per-intent content branching lives, as pure data. The PDF
and DOCX backends (``renderer.py``) just map each block type to their primitives,
so the two outputs stay consistent from one source (FR-RND-01).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from wapp_planner.documents.branding import Branding
from wapp_planner.documents.content import ExecutionPlanContent, QuoteContent


@dataclass(frozen=True)
class Heading:
    text: str
    level: int


@dataclass(frozen=True)
class Paragraph:
    text: str


@dataclass(frozen=True)
class Bullets:
    title: str
    items: list[str]


@dataclass(frozen=True)
class Table:
    headers: list[str]
    rows: list[list[str]] = field(default_factory=list)


@dataclass(frozen=True)
class KeyValues:
    pairs: list[tuple[str, str]]


Block = Heading | Paragraph | Bullets | Table | KeyValues


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _branding_header(branding: Branding) -> list[Block]:
    blocks: list[Block] = [Heading(branding.company_name, 1)]
    if branding.address:
        blocks.append(Paragraph(branding.address))
    if branding.contact:
        blocks.append(Paragraph(branding.contact))
    return blocks


def _quote_blocks(content: QuoteContent, branding: Branding) -> list[Block]:
    blocks = _branding_header(branding)
    blocks.append(Heading(content.title, 2))
    blocks.append(KeyValues([("Prepared for", content.prepared_for)]))
    blocks.append(Heading("Scope", 2))
    blocks.append(Paragraph(content.scope_summary))
    blocks.append(
        Table(
            ["Description", "Qty", "Unit", "Unit price", "Total"],
            [
                [
                    item.description,
                    f"{item.quantity:g}",
                    item.unit,
                    _money(item.unit_price),
                    _money(item.total),
                ]
                for item in content.line_items
            ],
        )
    )
    blocks.append(
        KeyValues(
            [
                ("Subtotal", _money(content.subtotal)),
                ("Tax", content.tax or "TBD"),
                ("Total", _money(content.total)),
            ]
        )
    )
    if content.assumptions:
        blocks.append(Bullets("Assumptions", content.assumptions))
    if content.exclusions:
        blocks.append(Bullets("Exclusions", content.exclusions))
    if content.validity:
        blocks.append(Paragraph(f"Validity: {content.validity}"))
    if content.notes:
        blocks.append(Paragraph(f"Notes: {content.notes}"))
    if branding.quote_terms:
        blocks.append(Paragraph(branding.quote_terms))
    return blocks


def _plan_blocks(content: ExecutionPlanContent, branding: Branding) -> list[Block]:
    blocks = _branding_header(branding)
    blocks.append(Heading(content.title, 2))
    blocks.append(Heading("Overview", 2))
    blocks.append(Paragraph(content.overview))
    if content.materials:
        blocks.append(Bullets("Materials & tools", content.materials))
    for index, phase in enumerate(content.phases, start=1):
        blocks.append(Heading(f"Phase {index}: {phase.name}", 2))
        blocks.append(Paragraph(f"Objective: {phase.objective}"))
        blocks.append(Bullets("Steps", phase.steps))
        if phase.safety_notes:
            blocks.append(Paragraph(f"Safety / code: {phase.safety_notes}"))
        if phase.dependencies:
            blocks.append(Bullets("Dependencies", phase.dependencies))
        if phase.estimated_duration:
            blocks.append(Paragraph(f"Estimated duration: {phase.estimated_duration}"))
    if content.quality_checkpoints:
        blocks.append(Bullets("Quality checkpoints", content.quality_checkpoints))
    if content.cleanup:
        blocks.append(Paragraph(f"Cleanup & handover: {content.cleanup}"))
    if content.notes:
        blocks.append(Paragraph(f"Notes: {content.notes}"))
    return blocks


def build_blocks(content: QuoteContent | ExecutionPlanContent, branding: Branding) -> list[Block]:
    """Convert document content into an ordered list of layout blocks."""
    if isinstance(content, QuoteContent):
        return _quote_blocks(content, branding)
    return _plan_blocks(content, branding)
