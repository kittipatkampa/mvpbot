"""HTTP API tests (no real LLM)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessageChunk

from assistant_service import db
from assistant_service.config import settings


class FakeCompiledGraph:
    def __init__(self, chunks: list):
        self._chunks = chunks

    async def astream(self, *args, **kwargs):
        for c in self._chunks:
            yield c


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_threads_crud(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "x")

    r = await client.post("/api/threads")
    assert r.status_code == 200
    tid = r.json()["thread_id"]

    r = await client.get("/api/threads")
    assert r.status_code == 200
    assert any(t["id"] == tid for t in r.json())

    r = await client.patch(f"/api/threads/{tid}", json={"title": "Hello", "archived": False})
    assert r.status_code == 200

    r = await client.get(f"/api/threads/{tid}/messages")
    assert r.status_code == 200
    assert r.json() == []

    r = await client.delete(f"/api/threads/{tid}")
    assert r.status_code == 200

    r = await client.get(f"/api/threads/{tid}/messages")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_chat_sse_streams_reasoning_and_tokens(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    patch_graph,
):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")

    tid = await db.create_thread()
    fake = FakeCompiledGraph(
        [
            (
                AIMessageChunk(
                    content="",
                    content_blocks=[{"type": "reasoning", "reasoning": "think"}],
                ),
                {"langgraph_node": "math_agent"},
            ),
            (
                AIMessageChunk(
                    content="",
                    content_blocks=[{"type": "text", "text": "ans"}],
                ),
                {"langgraph_node": "math_agent"},
            ),
        ]
    )
    patch_graph(fake)

    r = await client.post(
        "/api/chat",
        json={"thread_id": tid, "message": "1+1"},
    )
    assert r.status_code == 200
    body = r.text
    assert "reasoning" in body
    assert "token" in body or '"type": "token"' in body

    lines = [ln for ln in body.split("\n") if ln.startswith("data: ")]
    payloads = [json.loads(ln[6:]) for ln in lines if ln[6:].strip()]
    types = [p.get("type") for p in payloads]
    assert "reasoning" in types
    assert "token" in types
    assert "done" in types

    msgs = await db.get_messages(tid)
    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant"]
    assert msgs[-1]["content"] == "ans"
    assert msgs[-1]["reasoning"] == "think"


@pytest.mark.asyncio
async def test_chat_regenerate_replaces_assistant_without_duplicate_user(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    patch_graph,
):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")

    tid = await db.create_thread()
    first = FakeCompiledGraph(
        [
            (
                AIMessageChunk(
                    content="",
                    content_blocks=[{"type": "text", "text": "first"}],
                ),
                {"langgraph_node": "math_agent"},
            ),
        ]
    )
    patch_graph(first)

    r = await client.post(
        "/api/chat",
        json={"thread_id": tid, "message": "hello"},
    )
    assert r.status_code == 200
    msgs = await db.get_messages(tid)
    assert len(msgs) == 2
    assert msgs[1]["content"] == "first"

    second = FakeCompiledGraph(
        [
            (
                AIMessageChunk(
                    content="",
                    content_blocks=[{"type": "text", "text": "second"}],
                ),
                {"langgraph_node": "math_agent"},
            ),
        ]
    )
    patch_graph(second)

    r = await client.post(
        "/api/chat",
        json={"thread_id": tid, "message": "hello", "regenerate": True},
    )
    assert r.status_code == 200
    msgs = await db.get_messages(tid)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "second"


@pytest.mark.asyncio
async def test_chat_requires_api_key(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    tid = await db.create_thread()
    r = await client.post("/api/chat", json={"thread_id": tid, "message": "hi"})
    assert r.status_code == 200
    assert "error" in r.text


class FakeCompiledGraphCapturingConfig:
    """Fake graph that records the config passed to astream()."""

    def __init__(self, chunks: list):
        self._chunks = chunks
        self.last_config: dict | None = None

    async def astream(self, *args, **kwargs):
        self.last_config = kwargs.get("config")
        for c in self._chunks:
            yield c


@pytest.mark.asyncio
async def test_chat_passes_langfuse_callbacks_to_graph(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    patch_graph,
):
    """When Langfuse is configured, the handler is passed to graph.astream() callbacks."""
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")

    mock_handler = MagicMock()
    monkeypatch.setattr(
        "assistant_service.main.get_langfuse_handler",
        lambda session_id=None, user_id=None: (mock_handler, {"langfuse_session_id": session_id}),
    )

    tid = await db.create_thread()
    fake = FakeCompiledGraphCapturingConfig(
        [
            (
                AIMessageChunk(
                    content="",
                    content_blocks=[{"type": "text", "text": "hi"}],
                ),
                {"langgraph_node": "general_agent"},
            ),
        ]
    )
    patch_graph(fake)

    r = await client.post("/api/chat", json={"thread_id": tid, "message": "hello"})
    assert r.status_code == 200

    assert fake.last_config is not None, "graph.astream() was not called with a config"
    callbacks = fake.last_config.get("callbacks", [])
    assert mock_handler in callbacks, "Langfuse handler was not in the callbacks list"
    assert fake.last_config.get("metadata", {}).get("langfuse_session_id") == tid


@pytest.mark.asyncio
async def test_chat_omits_callbacks_when_langfuse_not_configured(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    patch_graph,
):
    """When Langfuse is not configured, callbacks list is empty."""
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(
        "assistant_service.main.get_langfuse_handler",
        lambda session_id=None, user_id=None: (None, {}),
    )

    tid = await db.create_thread()
    fake = FakeCompiledGraphCapturingConfig(
        [
            (
                AIMessageChunk(
                    content="",
                    content_blocks=[{"type": "text", "text": "ok"}],
                ),
                {"langgraph_node": "general_agent"},
            ),
        ]
    )
    patch_graph(fake)

    r = await client.post("/api/chat", json={"thread_id": tid, "message": "hello"})
    assert r.status_code == 200

    assert fake.last_config is not None
    callbacks = fake.last_config.get("callbacks", [])
    assert callbacks == [], f"Expected empty callbacks, got {callbacks}"
