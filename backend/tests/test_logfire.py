"""Tests for Logfire observability integration."""

from __future__ import annotations

import unittest.mock as mock

import logfire
import logfire.testing


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
