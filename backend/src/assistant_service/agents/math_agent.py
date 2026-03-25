"""Math subagent with extended thinking."""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic

from assistant_service.config import settings


def build_math_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.agent_model,
        max_tokens=settings.max_tokens,
        thinking={"type": "enabled", "budget_tokens": settings.thinking_budget_tokens},
        api_key=settings.anthropic_api_key or None,
    )


MATH_SYSTEM = (
    "You are a math and computation specialist. "
    "Show clear step-by-step reasoning in your answer when helpful. "
    "Be precise with notation and units."
)
