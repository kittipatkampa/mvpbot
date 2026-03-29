"""Logfire observability helpers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import logfire

from assistant_service.config import settings

_logfire_enabled: bool = False


def init_logfire() -> None:
    """Initialize Logfire and auto-instrument Anthropic calls.

    Call once at application startup (e.g. in the FastAPI lifespan handler).
    If LOGFIRE_TOKEN is not set, this is a no-op and the app runs without
    tracing.

    Logfire uses OpenTelemetry under the hood — no callbacks need to be passed
    to graph.astream(); all Anthropic calls are captured automatically.
    """
    global _logfire_enabled
    if not settings.logfire_token:
        return
    logfire.configure(token=settings.logfire_token)
    logfire.instrument_anthropic()
    _logfire_enabled = True


@asynccontextmanager
async def chat_span(
    thread_id: str,
    user_id: str | None = None,
    device_id: str | None = None,
) -> AsyncGenerator[None, None]:
    """Async context manager that wraps a chat request in a Logfire span.

    Attaches ``thread_id``, ``user_id``, and ``device_id`` as span attributes
    so they appear on every trace in the Logfire UI. When Logfire is not
    configured this is a transparent no-op.

    Usage::

        async with chat_span(thread_id=body.thread_id, user_id=user_id, device_id=device_id):
            async for chunk in graph.astream(...):
                ...
    """
    if not _logfire_enabled:
        yield
        return

    attrs: dict[str, str] = {"thread_id": thread_id}
    if user_id:
        attrs["user_id"] = user_id
    if device_id:
        attrs["device_id"] = device_id

    with logfire.span("chat thread_id={thread_id}", **attrs):
        yield
