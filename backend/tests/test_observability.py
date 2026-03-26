"""Tests for Langfuse observability helpers."""

from __future__ import annotations

import pytest

import assistant_service.observability as obs_module
from assistant_service.config import settings
from assistant_service.observability import get_langfuse_handler, init_langfuse


@pytest.fixture(autouse=True)
def reset_langfuse_client():
    """Ensure the module-level client is reset between tests."""
    original = obs_module._langfuse_client
    yield
    obs_module._langfuse_client = original


def test_get_langfuse_handler_returns_none_when_client_not_initialized():
    obs_module._langfuse_client = None
    handler, metadata = get_langfuse_handler()
    assert handler is None
    assert metadata == {}


def test_get_langfuse_handler_returns_none_with_empty_keys(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "langfuse_public_key", "")
    monkeypatch.setattr(settings, "langfuse_secret_key", "")
    obs_module._langfuse_client = None
    init_langfuse()
    handler, metadata = get_langfuse_handler()
    assert handler is None
    assert metadata == {}


def test_init_langfuse_does_nothing_when_keys_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "langfuse_public_key", "")
    monkeypatch.setattr(settings, "langfuse_secret_key", "")
    obs_module._langfuse_client = None
    init_langfuse()
    assert obs_module._langfuse_client is None


def test_init_langfuse_creates_client_when_keys_set(monkeypatch: pytest.MonkeyPatch):
    from langfuse import Langfuse

    monkeypatch.setattr(settings, "langfuse_public_key", "pk-lf-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-lf-test")
    monkeypatch.setattr(settings, "langfuse_host", "https://cloud.langfuse.com")
    obs_module._langfuse_client = None
    init_langfuse()
    assert isinstance(obs_module._langfuse_client, Langfuse)


def test_get_langfuse_handler_returns_handler_when_client_initialized(
    monkeypatch: pytest.MonkeyPatch,
):
    from unittest.mock import MagicMock

    from langfuse.langchain import CallbackHandler

    obs_module._langfuse_client = MagicMock()

    handler, metadata = get_langfuse_handler()
    assert isinstance(handler, CallbackHandler)
    assert metadata == {}


def test_get_langfuse_handler_includes_session_id_in_metadata(
    monkeypatch: pytest.MonkeyPatch,
):
    from unittest.mock import MagicMock

    obs_module._langfuse_client = MagicMock()

    handler, metadata = get_langfuse_handler(session_id="thread-abc")
    assert handler is not None
    assert metadata.get("langfuse_session_id") == "thread-abc"


def test_get_langfuse_handler_includes_user_id_in_metadata():
    from unittest.mock import MagicMock

    obs_module._langfuse_client = MagicMock()

    handler, metadata = get_langfuse_handler(user_id="user-xyz")
    assert handler is not None
    assert metadata.get("langfuse_user_id") == "user-xyz"
