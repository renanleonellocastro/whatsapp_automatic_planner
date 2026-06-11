"""Unit tests for the OpenAI provider adapters (AD-2)."""

from __future__ import annotations

from typing import Any

import pytest

from wapp_planner.providers.openai_provider import (
    OpenAILLMProvider,
    OpenAITranscriptionProvider,
    OpenAIVisionProvider,
    estimate_cost,
)


class _Usage:
    def __init__(self, prompt: int, completion: int) -> None:
        self.prompt_tokens = prompt
        self.completion_tokens = completion


class _Message:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str | None) -> None:
        self.message = _Message(content)


class _ChatResponse:
    def __init__(self, content: str | None, usage: _Usage) -> None:
        self.choices = [_Choice(content)]
        self.usage = usage


class _Completions:
    def __init__(self, response: _ChatResponse) -> None:
        self._response = response
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> _ChatResponse:
        self.kwargs = kwargs
        return self._response


class _Transcriptions:
    def __init__(self, text: str) -> None:
        self._text = text
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return type("T", (), {"text": self._text})()


class _FakeOpenAI:
    def __init__(self, *, chat: _ChatResponse | None = None, transcript: str = "") -> None:
        self.chat = type("Chat", (), {"completions": _Completions(chat)})() if chat else None
        self.audio = type("Audio", (), {"transcriptions": _Transcriptions(transcript)})()


def test_estimate_cost_known_and_unknown_model() -> None:
    assert estimate_cost("gpt-4o", 1000, 1000) == pytest.approx(0.0025 + 0.01)
    assert estimate_cost("mystery-model", 1000, 1000) == 0.0


def test_llm_complete_maps_response_and_usage() -> None:
    client = _FakeOpenAI(chat=_ChatResponse("hello", _Usage(100, 200)))
    result = OpenAILLMProvider(client).complete(
        system="s", user="u", model="gpt-4o", temperature=0.3, max_tokens=50
    )
    assert result.text == "hello"
    assert result.input_tokens == 100
    assert result.output_tokens == 200
    assert result.cost_usd == pytest.approx(estimate_cost("gpt-4o", 100, 200))
    kwargs = client.chat.completions.kwargs
    assert kwargs["temperature"] == 0.3
    assert kwargs["messages"][0]["role"] == "system"


def test_llm_complete_handles_null_content() -> None:
    client = _FakeOpenAI(chat=_ChatResponse(None, _Usage(1, 1)))
    assert OpenAILLMProvider(client).complete(system="s", user="u", model="gpt-4o").text == ""


def test_transcription() -> None:
    client = _FakeOpenAI(transcript="spoken words")
    result = OpenAITranscriptionProvider(client).transcribe(
        b"audio", model="gpt-4o-transcribe", mime_type="audio/ogg"
    )
    assert result.text == "spoken words"
    assert result.model == "gpt-4o-transcribe"


def test_vision_sends_data_url_and_returns_text() -> None:
    client = _FakeOpenAI(chat=_ChatResponse("a tiled wall", _Usage(1, 1)))
    text = OpenAIVisionProvider(client).describe(
        b"img", model="gpt-4o", mime_type="image/jpeg", prompt="describe"
    )
    assert text == "a tiled wall"
    content = client.chat.completions.kwargs["messages"][0]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_vision_handles_null_content() -> None:
    client = _FakeOpenAI(chat=_ChatResponse(None, _Usage(1, 1)))
    assert (
        OpenAIVisionProvider(client).describe(
            b"img", model="gpt-4o", mime_type="image/png", prompt="p"
        )
        == ""
    )
