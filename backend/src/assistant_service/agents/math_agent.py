"""Math subagent with extended thinking."""

from __future__ import annotations

from langchain_openrouter import ChatOpenRouter

from assistant_service.config import settings


def build_math_llm() -> ChatOpenRouter:
    return ChatOpenRouter(
        model=settings.agent_model,
        max_tokens=settings.agent_max_tokens,
        reasoning=settings.agent_reasoning or None,
        api_key=settings.openrouter_api_key or None,
    )


MATH_SYSTEM = (
    "You are a math and computation specialist. "
    "Show clear step-by-step reasoning in your answer when helpful. "
    "Be precise with notation and units."
)
