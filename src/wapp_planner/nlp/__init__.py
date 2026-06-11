"""Natural-language layer: intent classification (FR-CLS-*).

Document generation prompts/logic are added in a later phase.
"""

from wapp_planner.nlp.classifier import (
    ClassificationError,
    ClassificationResult,
    Classifier,
    is_low_confidence,
)
from wapp_planner.nlp.prompts import (
    UnknownPromptVersionError,
    classification_system_prompt,
    generation_system_prompt,
)

__all__ = [
    "ClassificationError",
    "ClassificationResult",
    "Classifier",
    "is_low_confidence",
    "UnknownPromptVersionError",
    "classification_system_prompt",
    "generation_system_prompt",
]
