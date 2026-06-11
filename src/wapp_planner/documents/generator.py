"""Generate structured document content via the LLM (FR-GEN-*, FR-REV-02).

The model is asked for JSON matching the per-intent schema; the result is parsed
and validated into a :class:`QuoteContent` / :class:`ExecutionPlanContent`. A
transient LLM error or an unparseable/invalid response is retried with bounded
exponential backoff (FR-GEN-05); exhausting the retries raises
:class:`GenerationError`. On a revision, the previous content and the owner's
feedback are fed back so the model improves rather than restarts (FR-REV-02).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from time import sleep as _real_sleep
from typing import Any

from pydantic import BaseModel, ValidationError

from wapp_planner.documents.content import ExecutionPlanContent, QuoteContent
from wapp_planner.nlp.prompts import generation_system_prompt
from wapp_planner.providers.base import LLMProvider
from wapp_planner.util.jsonio import extract_json_object
from wapp_planner.workflow.enums import Intent

DocumentContent = QuoteContent | ExecutionPlanContent

_CONTENT_MODEL: dict[Intent, type[BaseModel]] = {
    Intent.QUOTE: QuoteContent,
    Intent.EXECUTION_PLAN: ExecutionPlanContent,
}

_SCHEMA_HINT: dict[Intent, str] = {
    Intent.QUOTE: (
        'JSON schema: {"title": str, "prepared_for": str, "scope_summary": str, '
        '"line_items": [{"description": str, "quantity": number, "unit": str, '
        '"unit_price": number, "total": number}], "subtotal": number, '
        '"tax": str|null, "total": number, "assumptions": [str], '
        '"exclusions": [str], "validity": str|null, "notes": str|null}'
    ),
    Intent.EXECUTION_PLAN: (
        'JSON schema: {"title": str, "overview": str, "materials": [str], '
        '"phases": [{"name": str, "objective": str, "steps": [str], '
        '"safety_notes": str|null, "dependencies": [str], '
        '"estimated_duration": str|null}], "quality_checkpoints": [str], '
        '"cleanup": str|null, "notes": str|null}'
    ),
}


class GenerationError(Exception):
    """Raised when generation fails after exhausting all attempts."""


@dataclass(frozen=True)
class GeneratedDocument:
    """A successfully generated, validated document plus LLM usage metadata."""

    content: DocumentContent
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    attempts: int

    @property
    def structured_content(self) -> dict[str, Any]:
        """The content as a plain dict for persistence/rendering."""
        return self.content.model_dump()


class Generator:
    """Produces structured document content for a confirmed intent."""

    def __init__(
        self,
        llm: LLMProvider,
        *,
        model: str,
        prompt_version: str,
        max_attempts: int = 3,
        backoff_base_seconds: float = 0.5,
        sleep: Callable[[float], None] = _real_sleep,
    ) -> None:
        self._llm = llm
        self._model = model
        self._prompt_version = prompt_version
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base_seconds
        self._sleep = sleep

    def generate(
        self,
        intent: Intent,
        transcript: str,
        *,
        client_name: str,
        revision_no: int = 0,
        feedback: str | None = None,
        previous_content: dict[str, Any] | None = None,
    ) -> GeneratedDocument:
        """Generate document content, retrying transient/parse failures."""
        system = generation_system_prompt(intent, self._prompt_version)
        user = self._build_user_prompt(intent, transcript, client_name, feedback, previous_content)

        last_exc: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                result = self._llm.complete(
                    system=system, user=user, model=self._model, temperature=0.2
                )
                content = self._parse(result.text, intent)
                return GeneratedDocument(
                    content=content,
                    model=result.model,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    cost_usd=result.cost_usd,
                    attempts=attempt + 1,
                )
            except Exception as exc:  # noqa: BLE001 - transient/parse failures are retryable
                last_exc = exc
                if attempt + 1 < self._max_attempts:
                    self._sleep(self._backoff_base * (2**attempt))
        raise GenerationError(
            f"generation failed after {self._max_attempts} attempts: {last_exc}"
        ) from last_exc

    def _build_user_prompt(
        self,
        intent: Intent,
        transcript: str,
        client_name: str,
        feedback: str | None,
        previous_content: dict[str, Any] | None,
    ) -> str:
        parts = [
            f"Client: {client_name}",
            f"Request transcript:\n{transcript}",
        ]
        if previous_content is not None and feedback is not None:
            parts.append(
                "You previously produced this document:\n"
                f"{json.dumps(previous_content)}\n\n"
                f"The owner requested this revision: {feedback}\n"
                "Improve the existing document accordingly; do not start over."
            )
        parts.append(_SCHEMA_HINT[intent])
        return "\n\n".join(parts)

    def _parse(self, text: str, intent: Intent) -> DocumentContent:
        snippet = extract_json_object(text)  # ValueError -> retryable
        data = json.loads(snippet)  # JSONDecodeError -> retryable
        model = _CONTENT_MODEL[intent]
        try:
            return model(**data)  # type: ignore[return-value]
        except ValidationError as exc:
            raise ValueError(f"invalid {intent.value} content: {exc}") from exc
