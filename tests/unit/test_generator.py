"""Unit tests for document generation (FR-GEN-*, FR-REV-02)."""

from __future__ import annotations

import json

import pytest

from wapp_planner.documents.content import ExecutionPlanContent, QuoteContent
from wapp_planner.documents.generator import GeneratedDocument, GenerationError, Generator
from wapp_planner.nlp.prompts import (
    UnknownPromptVersionError,
    generation_system_prompt,
)
from wapp_planner.providers.base import LLMProvider, LLMResult
from wapp_planner.workflow.enums import Intent

QUOTE_JSON = json.dumps(
    {
        "title": "Kitchen Remodel Estimate",
        "prepared_for": "End Customer",
        "scope_summary": "Full kitchen remodel",
        "line_items": [
            {
                "description": "Demolition",
                "quantity": 1,
                "unit": "job",
                "unit_price": 500,
                "total": 500,
            }
        ],
        "subtotal": 500,
        "tax": "TBD",
        "total": 500,
        "assumptions": ["site accessible"],
        "exclusions": ["permits"],
    }
)

PLAN_JSON = json.dumps(
    {
        "title": "Install Plan",
        "overview": "Install cabinets",
        "materials": ["cabinets", "screws"],
        "phases": [{"name": "Prep", "objective": "ready site", "steps": ["clear area"]}],
        "quality_checkpoints": ["level check"],
    }
)


class ScriptedLLM(LLMProvider):
    """Returns/raises a scripted sequence of actions, recording calls."""

    def __init__(self, actions: list[object]) -> None:
        self._actions = list(actions)
        self.calls: list[dict[str, object]] = []

    def complete(self, *, system, user, model, temperature=0.0, max_tokens=None):  # type: ignore[no-untyped-def]
        self.calls.append({"system": system, "user": user, "model": model})
        action = self._actions.pop(0)
        if isinstance(action, Exception):
            raise action
        assert isinstance(action, LLMResult)
        return action


def _generator(actions: list[object], **kw: object) -> tuple[Generator, ScriptedLLM, list[float]]:
    llm = ScriptedLLM(actions)
    sleeps: list[float] = []
    gen = Generator(
        llm,
        model="gpt-4o",
        prompt_version="v1",
        sleep=lambda d: sleeps.append(d),
        **kw,  # type: ignore[arg-type]
    )
    return gen, llm, sleeps


def _ok(text: str) -> LLMResult:
    return LLMResult(text=text, model="gpt-4o", input_tokens=100, output_tokens=200, cost_usd=0.01)


# ── prompts ─────────────────────────────────────────────────────────────
def test_generation_prompt_per_intent() -> None:
    assert "QUOTE" in generation_system_prompt(Intent.QUOTE, "v1")
    assert "EXECUTION PLAN" in generation_system_prompt(Intent.EXECUTION_PLAN, "v1")


def test_generation_prompt_unknown_version() -> None:
    with pytest.raises(UnknownPromptVersionError):
        generation_system_prompt(Intent.QUOTE, "v9")


def test_generation_prompt_none_intent_invalid() -> None:
    with pytest.raises(ValueError, match="no generation prompt"):
        generation_system_prompt(Intent.NONE, "v1")


# ── generation happy paths ──────────────────────────────────────────────
def test_generate_quote() -> None:
    gen, llm, _ = _generator([_ok(QUOTE_JSON)])
    doc = gen.generate(Intent.QUOTE, "need a quote", client_name="Bob")
    assert isinstance(doc, GeneratedDocument)
    assert isinstance(doc.content, QuoteContent)
    assert doc.content.title == "Kitchen Remodel Estimate"
    assert doc.attempts == 1
    assert doc.input_tokens == 100
    assert doc.cost_usd == 0.01
    assert doc.structured_content["total"] == 500
    assert "QUOTE" in llm.calls[0]["system"]


def test_generate_execution_plan() -> None:
    gen, _, _ = _generator([_ok(PLAN_JSON)])
    doc = gen.generate(Intent.EXECUTION_PLAN, "plan it", client_name="Bob")
    assert isinstance(doc.content, ExecutionPlanContent)
    assert doc.content.phases[0].name == "Prep"


def test_generate_parses_json_in_prose() -> None:
    gen, _, _ = _generator([_ok(f"Here you go: {QUOTE_JSON} (let me know!)")])
    doc = gen.generate(Intent.QUOTE, "t", client_name="Bob")
    assert doc.content.subtotal == 500


# ── retries ─────────────────────────────────────────────────────────────
def test_retries_then_succeeds_with_backoff() -> None:
    gen, _, sleeps = _generator([_ok("not json"), _ok("still not"), _ok(QUOTE_JSON)])
    doc = gen.generate(Intent.QUOTE, "t", client_name="Bob")
    assert doc.attempts == 3
    assert sleeps == [0.5, 1.0]  # base * 2**attempt for attempts 0 and 1


def test_retries_on_llm_exception() -> None:
    gen, llm, sleeps = _generator([RuntimeError("503 transient"), _ok(QUOTE_JSON)])
    doc = gen.generate(Intent.QUOTE, "t", client_name="Bob")
    assert doc.attempts == 2
    assert len(llm.calls) == 2
    assert sleeps == [0.5]


def test_exhausts_attempts_raises_generation_error() -> None:
    gen, _, sleeps = _generator([_ok("nope"), _ok("nope2")], max_attempts=2)
    with pytest.raises(GenerationError, match="after 2 attempts"):
        gen.generate(Intent.QUOTE, "t", client_name="Bob")
    assert sleeps == [0.5]  # one sleep between the two attempts


@pytest.mark.parametrize(
    "bad",
    ["no braces here", "{not valid json}", '{"title": "x"}'],  # no-json, bad-json, invalid-content
)
def test_each_failure_kind_is_retryable(bad: str) -> None:
    gen, _, _ = _generator([_ok(bad)], max_attempts=1)
    with pytest.raises(GenerationError):
        gen.generate(Intent.QUOTE, "t", client_name="Bob")


# ── revision context (FR-REV-02) ────────────────────────────────────────
def test_revision_includes_previous_content_and_feedback() -> None:
    gen, llm, _ = _generator([_ok(QUOTE_JSON)])
    gen.generate(
        Intent.QUOTE,
        "t",
        client_name="Bob",
        revision_no=1,
        feedback="lower the demo price",
        previous_content={"title": "old"},
    )
    user_prompt = llm.calls[0]["user"]
    assert "lower the demo price" in user_prompt
    assert '"title": "old"' in user_prompt
    assert "do not start over" in user_prompt
