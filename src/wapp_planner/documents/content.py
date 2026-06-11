"""Structured document content models (FR-GEN-06, §11).

The LLM is asked to return JSON matching one of these schemas (per intent) so the
same structured content drives consistent PDF + DOCX rendering. Validating the
model's output here is also what makes a malformed generation retryable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    """A single priced line of a quote (§11)."""

    description: str
    quantity: float = Field(ge=0)
    unit: str
    unit_price: float = Field(ge=0)
    total: float = Field(ge=0)


class QuoteContent(BaseModel):
    """A cost estimate written in English for the end customer (FR-GEN-02)."""

    title: str
    prepared_for: str
    scope_summary: str
    line_items: list[LineItem]
    subtotal: float = Field(ge=0)
    # Owner fills tax per quote (AD-9); blank/"TBD" until then.
    tax: str | None = None
    total: float = Field(ge=0)
    assumptions: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    validity: str | None = None
    notes: str | None = None


class Phase(BaseModel):
    """One sequential phase of an execution plan (§11)."""

    name: str
    objective: str
    steps: list[str]
    safety_notes: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    estimated_duration: str | None = None


class ExecutionPlanContent(BaseModel):
    """A detailed step-by-step execution plan (FR-GEN-03)."""

    title: str
    overview: str
    materials: list[str] = Field(default_factory=list)
    phases: list[Phase]
    quality_checkpoints: list[str] = Field(default_factory=list)
    cleanup: str | None = None
    notes: str | None = None
