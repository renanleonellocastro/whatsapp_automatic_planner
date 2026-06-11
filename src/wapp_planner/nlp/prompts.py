"""Versioned prompt templates (FR-CLS-02; generation prompts added later).

Prompts are versioned so a change is deliberate and auditable: a deployment
pins ``prompt_version`` and the exact text used is reproducible.
"""

from __future__ import annotations

from typing import Final

from wapp_planner.workflow.enums import Intent


class UnknownPromptVersionError(Exception):
    """Raised when a requested prompt version is not registered."""


_CLASSIFICATION_V1 = """\
You classify inbound WhatsApp messages for a US civil-construction / renovation
planning business. The owner's clients send job details and ask for one of:

- "quote": a detailed cost estimate / budget (often: "how much", "price",
  "estimate", "bid", "cotação", "orçamento").
- "execution_plan": a step-by-step plan for HOW to execute the work (often:
  "how do we do this", "steps", "plan the job", "planejamento", "etapas").

If the message is small talk, a greeting, or unrelated to either, classify it as
"none".

Decide the single best intent. Respond ONLY with a JSON object of the form:
{"intent": "quote" | "execution_plan" | "none", "confidence": <0.0-1.0>,
 "rationale": "<one short sentence>"}
"""

_CLASSIFICATION_PROMPTS: Final[dict[str, str]] = {"v1": _CLASSIFICATION_V1}


_GENERATION_QUOTE_V1 = """\
You are a senior estimator for a US civil-construction / renovation company.
From the client's request transcript, produce a detailed, professional cost
estimate (QUOTE) WRITTEN IN ENGLISH for the client to forward to their customer.
Be specific with line items, quantities and realistic unit prices. State your
assumptions and exclusions explicitly. Leave the tax field blank ("TBD") for the
owner to fill. Respond ONLY with a JSON object matching the requested schema.
"""

_GENERATION_PLAN_V1 = """\
You are a senior project planner for a US civil-construction / renovation
company. From the client's request transcript, produce a detailed, step-by-step
EXECUTION PLAN written in English describing exactly how to perform the work,
phase by phase, from preparation through cleanup and handover. Include materials,
safety/code notes, dependencies and time estimates. Respond ONLY with a JSON
object matching the requested schema.
"""

_GENERATION_PROMPTS: Final[dict[str, dict[Intent, str]]] = {
    "v1": {Intent.QUOTE: _GENERATION_QUOTE_V1, Intent.EXECUTION_PLAN: _GENERATION_PLAN_V1}
}


def classification_system_prompt(version: str) -> str:
    """Return the classification system prompt for ``version``."""
    try:
        return _CLASSIFICATION_PROMPTS[version]
    except KeyError:
        raise UnknownPromptVersionError(version) from None


def generation_system_prompt(intent: Intent, version: str) -> str:
    """Return the generation system prompt for ``intent`` at ``version``."""
    try:
        prompts = _GENERATION_PROMPTS[version]
    except KeyError:
        raise UnknownPromptVersionError(version) from None
    try:
        return prompts[intent]
    except KeyError:
        raise ValueError(f"no generation prompt for intent {intent.value!r}") from None
