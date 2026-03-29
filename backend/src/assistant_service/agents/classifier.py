"""Intent classifier using Claude Haiku + structured output."""

from __future__ import annotations

import logging
from typing import Literal

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from assistant_service.config import settings

logger = logging.getLogger(__name__)


class IntentClassification(BaseModel):
    intent: Literal["math", "general"] = Field(
        description="math: mathematics, computation, equations, code math; general: everything else"
    )


def build_classifier_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.classifier_model,
        max_tokens=settings.classifier_max_tokens,
        api_key=settings.anthropic_api_key or None,
    )


def classify_intent_text(user_text: str) -> IntentClassification:
    preview = user_text[:80] + ("…" if len(user_text) > 80 else "")
    logger.debug("classify_intent_text: input=%r model=%s", preview, settings.classifier_model)
    llm = build_classifier_llm()
    structured = llm.with_structured_output(IntentClassification)
    result = structured.invoke(
        [
            {
                "role": "system",
                "content": (
                    "Classify the user's latest message intent.\n"
                    "- math: mathematics, arithmetic, algebra, calculus, statistics, "
                    "numerical computation, programming that is primarily about math.\n"
                    "- general: general knowledge, explanations, facts, non-math tasks.\n"
                    "Reply with JSON only matching the schema."
                ),
            },
            {"role": "user", "content": user_text},
        ]
    )
    logger.debug("classify_intent_text: result=%s", result.intent)
    return result
