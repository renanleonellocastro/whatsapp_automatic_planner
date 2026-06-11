"""OpenAI-backed provider adapters (AD-2).

Thin adapters over an injected OpenAI client (``openai.OpenAI``) implementing the
LLM, transcription and vision interfaces. The client is injected so these are
unit-tested with a fake exposing the same attribute shape — no network.

Token usage is mapped to an estimated cost via :data:`PRICE_PER_1K_USD` for
cost tracking (NFR-COST-01); unknown models cost 0.
"""

from __future__ import annotations

import base64
from typing import Any, Final, Protocol

from wapp_planner.providers.base import (
    LLMProvider,
    LLMResult,
    TranscriptionProvider,
    TranscriptionResult,
    VisionProvider,
)

#: Rough (input, output) USD price per 1K tokens. Extend as needed.
PRICE_PER_1K_USD: Final[dict[str, tuple[float, float]]] = {
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
}


class _OpenAIClient(Protocol):  # pragma: no cover - structural typing only
    @property
    def chat(self) -> Any: ...
    @property
    def audio(self) -> Any: ...


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a completion from the price table."""
    prices = PRICE_PER_1K_USD.get(model)
    if prices is None:
        return 0.0
    input_price, output_price = prices
    return (input_tokens / 1000) * input_price + (output_tokens / 1000) * output_price


class OpenAILLMProvider(LLMProvider):
    """Chat-completion LLM via OpenAI."""

    def __init__(self, client: _OpenAIClient) -> None:
        self._client = client

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> LLMResult:
        response = self._client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        return LLMResult(
            text=response.choices[0].message.content or "",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=estimate_cost(model, input_tokens, output_tokens),
        )


class OpenAITranscriptionProvider(TranscriptionProvider):
    """Speech-to-text via OpenAI audio transcription."""

    def __init__(self, client: _OpenAIClient) -> None:
        self._client = client

    def transcribe(
        self, audio: bytes, *, model: str, mime_type: str | None = None
    ) -> TranscriptionResult:
        response = self._client.audio.transcriptions.create(
            model=model, file=("audio", audio, mime_type or "application/octet-stream")
        )
        return TranscriptionResult(text=response.text, model=model)


class OpenAIVisionProvider(VisionProvider):
    """Image description via an OpenAI multimodal chat completion."""

    def __init__(self, client: _OpenAIClient) -> None:
        self._client = client

    def describe(self, image: bytes, *, model: str, mime_type: str, prompt: str) -> str:
        data_url = f"data:{mime_type};base64,{base64.b64encode(image).decode('ascii')}"
        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )
        return response.choices[0].message.content or ""
