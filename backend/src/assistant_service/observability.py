"""Arize Phoenix observability helpers."""

from __future__ import annotations

from assistant_service.config import settings


def init_phoenix() -> None:
    """Initialize Arize Phoenix and auto-instrument LangChain/LangGraph.

    Call once at application startup (e.g. in the FastAPI lifespan handler).
    Uses OpenTelemetry instrumentation — no callbacks need to be passed to
    graph.astream(); all LangChain calls are captured automatically.

    Self-hosted (default):
        Run Phoenix locally:  python -m phoenix.server.main
        Set PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
        No API key required.

    Arize Phoenix Cloud:
        Set PHOENIX_API_KEY and PHOENIX_COLLECTOR_ENDPOINT to your cloud endpoint.
    """
    if not settings.phoenix_collector_endpoint:
        return

    from openinference.instrumentation.langchain import LangChainInstrumentor
    from phoenix.otel import register

    kwargs: dict = {"endpoint": settings.phoenix_collector_endpoint}
    if settings.phoenix_api_key:
        kwargs["headers"] = {"api_key": settings.phoenix_api_key}

    tracer_provider = register(**kwargs)
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
