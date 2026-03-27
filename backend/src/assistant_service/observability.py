"""Logfire observability helpers."""

from __future__ import annotations

import logfire

from assistant_service.config import settings


def init_logfire() -> None:
    """Initialize Logfire and auto-instrument LangChain/LangGraph.

    Call once at application startup (e.g. in the FastAPI lifespan handler).
    If LOGFIRE_TOKEN is not set, this is a no-op and the app runs without
    tracing.

    Logfire uses OpenTelemetry under the hood — no callbacks need to be passed
    to graph.astream(); all LangChain calls are captured automatically.
    """
    if not settings.logfire_token:
        return
    logfire.configure(token=settings.logfire_token)
    logfire.instrument_anthropic()
