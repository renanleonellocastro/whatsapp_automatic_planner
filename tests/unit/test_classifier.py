"""Unit tests for intent classification (FR-CLS-01/02/04)."""

from __future__ import annotations

import pytest

from wapp_planner.nlp.classifier import (
    ClassificationError,
    ClassificationResult,
    Classifier,
    is_low_confidence,
)
from wapp_planner.nlp.prompts import (
    UnknownPromptVersionError,
    classification_system_prompt,
)
from wapp_planner.providers.base import LLMResult
from wapp_planner.providers.fakes import FakeLLMProvider
from wapp_planner.workflow.enums import Intent


def _classifier(text: str) -> tuple[Classifier, FakeLLMProvider]:
    llm = FakeLLMProvider(responses=[LLMResult(text=text, model="gpt-4o")])
    return Classifier(llm, model="gpt-4o", prompt_version="v1"), llm


# ── prompts ─────────────────────────────────────────────────────────────
def test_known_prompt_version() -> None:
    assert "quote" in classification_system_prompt("v1")


def test_unknown_prompt_version_raises() -> None:
    with pytest.raises(UnknownPromptVersionError, match="v99"):
        classification_system_prompt("v99")


# ── classify ────────────────────────────────────────────────────────────
def test_classify_quote() -> None:
    clf, llm = _classifier('{"intent": "quote", "confidence": 0.92, "rationale": "asks price"}')
    result = clf.classify("how much for a bathroom remodel?")
    assert result.intent is Intent.QUOTE
    assert result.confidence == 0.92
    assert result.rationale == "asks price"
    # used the deterministic prompt + model
    assert llm.calls[0]["model"] == "gpt-4o"
    assert llm.calls[0]["temperature"] == 0.0
    assert "classify" in llm.calls[0]["system"].lower()


def test_classify_execution_plan() -> None:
    clf, _ = _classifier(
        '{"intent": "execution_plan", "confidence": 0.8, "rationale": "wants steps"}'
    )
    assert clf.classify("plan the install").intent is Intent.EXECUTION_PLAN


def test_classify_none() -> None:
    clf, _ = _classifier('{"intent": "none", "confidence": 0.99, "rationale": "greeting"}')
    result = clf.classify("hey good morning")
    assert result.intent is Intent.NONE
    assert not result.is_actionable


def test_classify_parses_json_inside_code_fence() -> None:
    fenced = '```json\n{"intent": "quote", "confidence": 0.7, "rationale": "x"}\n```'
    clf, _ = _classifier(fenced)
    assert clf.classify("t").intent is Intent.QUOTE


def test_classify_parses_json_surrounded_by_prose() -> None:
    text = (
        'Sure! Here is the result: {"intent": "quote", "confidence": 0.6, "rationale": "x"} Done.'
    )
    clf, _ = _classifier(text)
    assert clf.classify("t").confidence == 0.6


def test_classify_actionable_property() -> None:
    actionable = ClassificationResult(intent=Intent.QUOTE, confidence=0.5, rationale="r")
    not_actionable = ClassificationResult(intent=Intent.NONE, confidence=0.5, rationale="r")
    assert actionable.is_actionable
    assert not not_actionable.is_actionable


def test_classify_no_json_raises() -> None:
    clf, _ = _classifier("I think this is a quote but I won't format it")
    with pytest.raises(ClassificationError, match="no JSON object"):
        clf.classify("t")


def test_classify_malformed_json_raises() -> None:
    clf, _ = _classifier('{"intent": "quote", "confidence": }')
    with pytest.raises(ClassificationError, match="invalid JSON"):
        clf.classify("t")


def test_classify_invalid_intent_value_raises() -> None:
    clf, _ = _classifier('{"intent": "banana", "confidence": 0.5, "rationale": "x"}')
    with pytest.raises(ClassificationError, match="invalid classification fields"):
        clf.classify("t")


def test_classify_out_of_range_confidence_raises() -> None:
    clf, _ = _classifier('{"intent": "quote", "confidence": 1.5, "rationale": "x"}')
    with pytest.raises(ClassificationError, match="invalid classification fields"):
        clf.classify("t")


def test_classify_missing_field_raises() -> None:
    clf, _ = _classifier('{"intent": "quote"}')
    with pytest.raises(ClassificationError, match="invalid classification fields"):
        clf.classify("t")


# ── confidence policy ───────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("confidence", "threshold", "expected"),
    [(0.5, 0.6, True), (0.6, 0.6, False), (0.9, 0.6, False)],
)
def test_is_low_confidence(confidence: float, threshold: float, expected: bool) -> None:
    result = ClassificationResult(intent=Intent.QUOTE, confidence=confidence, rationale="r")
    assert is_low_confidence(result, threshold) is expected
