"""Tests for Logfire observability integration."""

from __future__ import annotations

import unittest.mock as mock

import logfire
import logfire.testing
import pytest


def test_logfire_info_emits_span(capfire: logfire.testing.CaptureLogfire):
    """logfire.info() should emit a span captured by the capfire fixture."""
    logfire.info("Hello from mvpbot!")

    # Spans store the rendered message in the `logfire.msg` attribute
    messages = [
        s.attributes.get("logfire.msg", "") or s.name
        for s in capfire.exporter.exported_spans
    ]
    assert any("Hello from mvpbot!" in m for m in messages)


def test_init_logfire_noop_without_token(monkeypatch):
    """init_logfire() must be a no-op when LOGFIRE_TOKEN is not set."""
    from assistant_service.config import settings
    from assistant_service.observability import init_logfire

    monkeypatch.setattr(settings, "logfire_token", "")

    with mock.patch("assistant_service.observability.logfire") as mock_logfire:
        init_logfire()
        mock_logfire.configure.assert_not_called()


def test_init_logfire_configures_when_token_set(monkeypatch):
    """init_logfire() calls logfire.configure() and instrument_anthropic() when token is present."""
    from assistant_service.config import settings
    from assistant_service.observability import init_logfire

    monkeypatch.setattr(settings, "logfire_token", "test-token-123")

    with mock.patch("assistant_service.observability.logfire") as mock_logfire:
        init_logfire()
        mock_logfire.configure.assert_called_once_with(token="test-token-123")
        mock_logfire.instrument_anthropic.assert_called_once()


@pytest.mark.asyncio
async def test_chat_span_emits_attributes(capfire: logfire.testing.CaptureLogfire):
    """chat_span() should emit a span with thread_id, user_id, device_id, and reasoning."""
    import assistant_service.observability as obs
    from assistant_service.observability import chat_span, set_span_attribute

    obs._logfire_enabled = True
    try:
        async with chat_span(
            thread_id="thread-abc",
            user_id="user-123",
            device_id="device-xyz",
        ):
            set_span_attribute("reasoning", "I thought about this carefully")
    finally:
        obs._logfire_enabled = False

    spans = capfire.exporter.exported_spans
    assert spans, "Expected at least one span"
    # The pending_span is exported when the span opens; the final closed span
    # (without 'logfire.span_type' == 'pending_span') carries all attributes
    # including those set after the span was opened (e.g. reasoning).
    final_spans = [
        s for s in spans
        if s.attributes.get("logfire.span_type") != "pending_span"
    ]
    assert final_spans, "Expected a closed span"
    attrs = final_spans[0].attributes or {}
    assert attrs.get("thread_id") == "thread-abc"
    assert attrs.get("user_id") == "user-123"
    assert attrs.get("device_id") == "device-xyz"
    assert attrs.get("reasoning") == "I thought about this carefully"


@pytest.mark.asyncio
async def test_chat_span_noop_when_disabled():
    """chat_span() must be a transparent no-op when Logfire is not enabled."""
    import assistant_service.observability as obs
    from assistant_service.observability import chat_span

    obs._logfire_enabled = False
    reached = False
    async with chat_span(thread_id="t", user_id="u", device_id="d"):
        reached = True
    assert reached
