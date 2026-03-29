"""Math subagent with extended thinking."""

from __future__ import annotations

import logging

from langchain_anthropic import ChatAnthropic

from assistant_service.config import settings

logger = logging.getLogger(__name__)


def build_math_llm() -> ChatAnthropic:
    logger.debug(
        "build_math_llm: model=%s max_tokens=%d thinking_budget=%d",
        settings.agent_model,
        settings.agent_max_tokens,
        settings.agent_thinking_budget_tokens,
    )
    return ChatAnthropic(
        model=settings.agent_model,
        max_tokens=settings.agent_max_tokens,
        thinking={"type": "enabled", "budget_tokens": settings.agent_thinking_budget_tokens},
        api_key=settings.anthropic_api_key or None,
    )


MATH_SYSTEM = (
    "You are a math and computation specialist. "
    "Show clear step-by-step reasoning in your answer when helpful. "
    "Be precise with notation and units."
)
