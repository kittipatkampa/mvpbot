"""FastAPI application: threads API + SSE chat."""

from __future__ import annotations

import json
import sqlite3
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from assistant_service import db
from assistant_service.config import settings
from assistant_service.graph import get_graph
from assistant_service.observability import get_langfuse_handler, init_langfuse
from assistant_service.models import (
    ChatRequest,
    MessageOut,
    ThreadCreateBody,
    ThreadCreateResponse,
    ThreadOut,
    ThreadPatchRequest,
)


def _rows_to_messages(rows: list[dict]) -> list[BaseMessage]:
    """Build LangChain messages for the model. Assistant uses text only (reasoning is UI-only in DB)."""
    out: list[BaseMessage] = []
    for r in rows:
        role = r["role"]
        content = r["content"] or ""
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
    return out


def _extract_blocks(chunk: Any) -> list[dict[str, Any]]:
    if hasattr(chunk, "content_blocks") and chunk.content_blocks:
        return list(chunk.content_blocks)
    # Fallback: plain content string
    c = getattr(chunk, "content", None)
    if c:
        return [{"type": "text", "text": c}]
    return []


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.init_db()
    init_langfuse()
    yield


app = FastAPI(title="Assistant Service", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/threads", response_model=ThreadCreateResponse)
async def create_thread(body: ThreadCreateBody | None = None):
    try:
        tid = await db.create_thread(thread_id=body.id if body and body.id else None)
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=409, detail="Thread id already exists") from e
    return ThreadCreateResponse(thread_id=tid)


@app.get("/api/threads", response_model=list[ThreadOut])
async def list_threads(q: str | None = None, include_archived: bool = False):
    rows = await db.list_threads(q=q, include_archived=include_archived)
    return [
        ThreadOut(
            id=r["id"],
            title=r["title"],
            updated_at=r["updated_at"],
            archived=bool(r["archived"]),
        )
        for r in rows
    ]


@app.get("/api/threads/{thread_id}", response_model=ThreadOut)
async def get_thread(thread_id: str):
    row = await db.get_thread(thread_id)
    if not row:
        raise HTTPException(status_code=404, detail="Thread not found")
    return ThreadOut(
        id=row["id"],
        title=row["title"],
        updated_at=row["updated_at"],
        archived=bool(row["archived"]),
    )


@app.patch("/api/threads/{thread_id}")
async def patch_thread(thread_id: str, body: ThreadPatchRequest):
    if body.title is None and body.archived is None:
        return {"ok": True}
    ok = await db.patch_thread(
        thread_id,
        title=body.title,
        archived=body.archived,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"ok": True}


@app.delete("/api/threads/{thread_id}")
async def delete_thread(thread_id: str):
    ok = await db.delete_thread(thread_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"ok": True}


@app.get("/api/threads/{thread_id}/messages", response_model=list[MessageOut])
async def get_messages(thread_id: str):
    if not await db.thread_exists(thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    rows = await db.get_messages(thread_id)
    return [
        MessageOut(
            id=r["id"],
            role=r["role"],
            content=r["content"] or "",
            reasoning=r.get("reasoning"),
            created_at=r["created_at"],
        )
        for r in rows
    ]


async def _sse_chat(body: ChatRequest):
    if not settings.anthropic_api_key:
        yield f"data: {json.dumps({'type': 'error', 'message': 'ANTHROPIC_API_KEY is not set'})}\n\n"
        return

    if not await db.thread_exists(body.thread_id):
        yield f"data: {json.dumps({'type': 'error', 'message': 'Thread not found'})}\n\n"
        return

    if body.regenerate:
        await db.delete_last_assistant_message(body.thread_id)
    else:
        await db.add_message(body.thread_id, "user", body.message)
        await db.maybe_set_thread_title_from_first_message(body.thread_id, body.message)

    rows = await db.get_messages(body.thread_id)
    if not rows:
        yield f"data: {json.dumps({'type': 'error', 'message': 'No messages to continue from'})}\n\n"
        return
    if rows[-1]["role"] != "user":
        yield f"data: {json.dumps({'type': 'error', 'message': 'Last message must be from user to run the model'})}\n\n"
        return

    lc_messages = _rows_to_messages(rows)

    graph = get_graph()
    full_reasoning = ""
    full_text = ""

    langfuse_handler, lf_metadata = get_langfuse_handler(session_id=body.thread_id)
    callbacks = [langfuse_handler] if langfuse_handler else []

    try:
        # stream_mode="messages" yields (AIMessageChunk | AIMessage, metadata dict)
        async for msg_chunk, _metadata in graph.astream(
            {"messages": lc_messages, "intent": ""},
            stream_mode="messages",
            config={"callbacks": callbacks, "metadata": lf_metadata},
        ):
            for block in _extract_blocks(msg_chunk):
                btype = block.get("type")
                if btype == "reasoning":
                    delta = block.get("reasoning") or ""
                    if delta:
                        full_reasoning += delta
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': delta})}\n\n"
                elif btype == "text":
                    delta = block.get("text") or ""
                    if delta:
                        full_text += delta
                        yield f"data: {json.dumps({'type': 'token', 'content': delta})}\n\n"
                elif btype == "thinking":
                    delta = block.get("thinking") or ""
                    if delta:
                        full_reasoning += delta
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': delta})}\n\n"

        reasoning_to_store = full_reasoning.strip() or None
        await db.add_message(
            body.thread_id,
            "assistant",
            full_text,
            reasoning=reasoning_to_store,
        )
    except Exception as e:
        err_msg = str(e).strip() or type(e).__name__
        yield f"data: {json.dumps({'type': 'error', 'message': err_msg})}\n\n"
    finally:
        yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.post("/api/chat")
async def chat(body: ChatRequest):
    return StreamingResponse(
        _sse_chat(body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def create_app() -> FastAPI:
    return app
