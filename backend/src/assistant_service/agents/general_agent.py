"""General knowledge subagent with reasoning via OpenRouter."""

from __future__ import annotations

import logging

from assistant_service.config import settings
from assistant_service.openrouter_llm import ChatOpenRouterWithReasoning

logger = logging.getLogger(__name__)


def build_general_llm() -> ChatOpenRouterWithReasoning:
    logger.debug(
        "build_general_llm: model=%s max_tokens=%d reasoning=%s",
        settings.agent_model,
        settings.agent_max_tokens,
        settings.agent_reasoning,
    )
    return ChatOpenRouterWithReasoning(
        model=settings.agent_model,
        max_tokens=settings.agent_max_tokens,
        reasoning=settings.agent_reasoning,
        api_key=settings.openrouter_api_key,
    )


GENERAL_SYSTEM = (
    "You are a helpful assistant for general knowledge questions. "
    "Give accurate, concise answers and cite uncertainty when appropriate."
)
