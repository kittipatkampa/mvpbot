"""Arize Phoenix observability helpers."""

from __future__ import annotations

import os

from assistant_service.config import settings


def init_phoenix() -> None:
    """Initialize Arize Phoenix and auto-instrument LangChain/LangGraph.

    Call once at application startup (e.g. in the FastAPI lifespan handler).
    Uses OpenTelemetry instrumentation — no callbacks need to be passed to
    graph.astream(); all LangChain calls are captured automatically.

    Self-hosted (default):
        Run Phoenix locally:  python -m phoenix.server.main
        Set PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006
        No API key required.

    Arize Phoenix Cloud:
        Set PHOENIX_API_KEY and PHOENIX_COLLECTOR_ENDPOINT to your space endpoint,
        e.g. https://app.phoenix.arize.com/s/<your-space-name>
        The SDK reads PHOENIX_API_KEY from the environment automatically.
    """
    if not settings.phoenix_collector_endpoint:
        return

    from openinference.instrumentation.langchain import LangChainInstrumentor
    from phoenix.otel import register

    # pydantic-settings loads .env into Settings but does NOT set OS env vars.
    # Pass api_key explicitly to register() so the SDK can authenticate,
    # and also set os.environ as a fallback for any SDK internals that read it.
    if settings.phoenix_api_key:
        os.environ["PHOENIX_API_KEY"] = settings.phoenix_api_key

    tracer_provider = register(
        endpoint=settings.phoenix_collector_endpoint,
        protocol="http/protobuf",
        batch=True,
        api_key=settings.phoenix_api_key or None,
    )
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
