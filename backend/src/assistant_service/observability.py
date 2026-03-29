"""Logfire observability helpers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import logfire
from opentelemetry import trace

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


def set_span_attribute(key: str, value: str) -> None:
    """Set an attribute on the currently active OpenTelemetry span.

    Used to attach dynamic values (e.g. accumulated reasoning text) to the
    chat span after streaming completes. No-op when Logfire is not configured
    or there is no active span.
    """
    if not _logfire_enabled:
        return
    span = trace.get_current_span()
    if span and span.is_recording():
        span.set_attribute(key, value)


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

    Call ``set_span_attribute()`` from within the context to attach additional
    attributes (e.g. the accumulated reasoning text) after streaming completes.

    Usage::

        async with chat_span(thread_id=body.thread_id, user_id=user_id, device_id=device_id):
            async for chunk in graph.astream(...):
                ...
            set_span_attribute("reasoning", full_reasoning)
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
