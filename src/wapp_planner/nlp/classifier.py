"""Intent classification over a normalized transcript (FR-CLS-01/02/04).

Uses the LLM with a versioned, deterministic (temperature 0) prompt and parses
the structured ``{intent, confidence, rationale}`` JSON response. Robust to the
model wrapping its JSON in prose or code fences; genuinely malformed responses
raise :class:`ClassificationError`.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field, ValidationError

from wapp_planner.nlp.prompts import classification_system_prompt
from wapp_planner.providers.base import LLMProvider
from wapp_planner.util.jsonio import extract_json_object
from wapp_planner.workflow.enums import Intent

_USER_TEMPLATE = (
    "Classify the following request transcript.\n\n"
    "Transcript:\n{transcript}\n\n"
    'Respond ONLY with JSON: {{"intent": "quote"|"execution_plan"|"none", '
    '"confidence": 0.0-1.0, "rationale": "..."}}'
)


class ClassificationError(Exception):
    """Raised when the classifier response cannot be parsed/validated."""


class ClassificationResult(BaseModel):
    """Structured classification outcome (FR-CLS-02)."""

    intent: Intent
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str

    @property
    def is_actionable(self) -> bool:
        """True for intents that should proceed to the owner (not NONE)."""
        return self.intent is not Intent.NONE


def is_low_confidence(result: ClassificationResult, threshold: float) -> bool:
    """Whether the result's confidence is below ``threshold`` (FR-CLS-04)."""
    return result.confidence < threshold


class Classifier:
    """Classifies a transcript into a :class:`ClassificationResult`."""

    def __init__(self, llm: LLMProvider, *, model: str, prompt_version: str) -> None:
        self._llm = llm
        self._model = model
        self._prompt_version = prompt_version

    def classify(self, transcript: str) -> ClassificationResult:
        system = classification_system_prompt(self._prompt_version)
        result = self._llm.complete(
            system=system,
            user=_USER_TEMPLATE.format(transcript=transcript),
            model=self._model,
            temperature=0.0,
        )
        return self._parse(result.text)

    def _parse(self, text: str) -> ClassificationResult:
        try:
            snippet = extract_json_object(text)
        except ValueError as exc:
            raise ClassificationError(str(exc)) from exc
        try:
            data = json.loads(snippet)
        except json.JSONDecodeError as exc:
            raise ClassificationError(f"invalid JSON in classifier response: {exc}") from exc
        # _extract_json guarantees a leading '{', so json.loads yields a dict.
        try:
            return ClassificationResult(**data)
        except ValidationError as exc:
            raise ClassificationError(f"invalid classification fields: {exc}") from exc
