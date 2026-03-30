"""HTTP API tests (no real LLM)."""

from __future__ import annotations

import json
from pathlib import Path

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


@pytest.mark.asyncio
async def test_anonymous_user_created_on_first_request(
    client: AsyncClient, db_path: Path
):
    device_id = "test-device-xyz-123"
    r = await client.post("/api/threads", headers={"X-Device-ID": device_id})
    assert r.status_code == 200

    # User row should now exist with the given device_id
    user_id = await db.get_or_create_user(device_id, db_path=db_path)
    assert user_id is not None


@pytest.mark.asyncio
async def test_threads_scoped_by_device_id(client: AsyncClient):
    device_a = {"X-Device-ID": "device-aaa"}
    device_b = {"X-Device-ID": "device-bbb"}

    # Create thread as device A
    r = await client.post("/api/threads", headers=device_a)
    assert r.status_code == 200
    tid_a = r.json()["thread_id"]

    # Device B should not see device A's thread
    r = await client.get("/api/threads", headers=device_b)
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()]
    assert tid_a not in ids

    # Device A can see its own thread
    r = await client.get("/api/threads", headers=device_a)
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()]
    assert tid_a in ids

    # Device B cannot GET/PATCH/DELETE device A's thread
    r = await client.get(f"/api/threads/{tid_a}", headers=device_b)
    assert r.status_code == 404

    r = await client.patch(
        f"/api/threads/{tid_a}", json={"title": "hack"}, headers=device_b
    )
    assert r.status_code == 404

    r = await client.delete(f"/api/threads/{tid_a}", headers=device_b)
    assert r.status_code == 404
