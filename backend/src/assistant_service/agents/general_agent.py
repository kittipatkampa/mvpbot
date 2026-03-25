"""General knowledge subagent with extended thinking."""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic

from assistant_service.config import settings


def build_general_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.agent_model,
        max_tokens=settings.max_tokens,
        thinking={"type": "enabled", "budget_tokens": settings.thinking_budget_tokens},
        api_key=settings.anthropic_api_key or None,
    )


GENERAL_SYSTEM = (
    "You are a helpful assistant for general knowledge questions. "
    "Give accurate, concise answers and cite uncertainty when appropriate."
)
