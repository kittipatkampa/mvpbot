"""FastAPI application: threads API + SSE chat."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from assistant_service import db
from assistant_service.agents.classifier import classify_intent_text
from assistant_service.config import settings
from assistant_service.demo_response import stream_demo
from assistant_service.graph import get_graph
from assistant_service.logging_config import configure_logging
from assistant_service.observability import init_phoenix
from assistant_service.models import (
    ChatRequest,
    MessageOut,
    ThreadCreateBody,
    ThreadCreateResponse,
    ThreadOut,
    ThreadPatchRequest,
)

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


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

    blocks: list[dict[str, Any]] = []

    # OpenRouter surfaces reasoning in additional_kwargs["reasoning_content"]
    reasoning = (getattr(chunk, "additional_kwargs", None) or {}).get("reasoning_content")
    if reasoning:
        blocks.append({"type": "reasoning", "reasoning": reasoning})

    c = getattr(chunk, "content", None)
    if c:
        blocks.append({"type": "text", "text": c})

    return blocks


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting up — log_level=%s", settings.log_level.upper())
    await db.init_db()
    logger.info("Database initialized at %s", settings.assistant_db_path)
    init_phoenix()
    yield
    logger.info("Shutting down")


app = FastAPI(title="Assistant Service", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_user_id(x_device_id: str | None = Header(default=None)) -> str | None:
    """Extract device_id from X-Device-ID header and resolve/create the anonymous user row."""
    if not x_device_id:
        return None  # permissive: no header = no user scoping (legacy/dev mode)
    return await db.get_or_create_user(x_device_id)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/threads", response_model=ThreadCreateResponse)
async def create_thread(
    body: ThreadCreateBody | None = None,
    user_id: str | None = Depends(get_user_id),
):
    try:
        tid = await db.create_thread(
            thread_id=body.id if body and body.id else None,
            user_id=user_id,
        )
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=409, detail="Thread id already exists") from e
    logger.info("Thread created thread_id=%s user_id=%s", tid, user_id)
    return ThreadCreateResponse(thread_id=tid)


@app.get("/api/threads", response_model=list[ThreadOut])
async def list_threads(
    q: str | None = None,
    include_archived: bool = False,
    user_id: str | None = Depends(get_user_id),
):
    rows = await db.list_threads(q=q, include_archived=include_archived, user_id=user_id)
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
async def get_thread(thread_id: str, user_id: str | None = Depends(get_user_id)):
    row = await db.get_thread(thread_id, user_id=user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Thread not found")
    return ThreadOut(
        id=row["id"],
        title=row["title"],
        updated_at=row["updated_at"],
        archived=bool(row["archived"]),
    )


@app.patch("/api/threads/{thread_id}")
async def patch_thread(
    thread_id: str,
    body: ThreadPatchRequest,
    user_id: str | None = Depends(get_user_id),
):
    if body.title is None and body.archived is None:
        return {"ok": True}
    ok = await db.patch_thread(
        thread_id,
        title=body.title,
        archived=body.archived,
        user_id=user_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"ok": True}


@app.delete("/api/threads/{thread_id}")
async def delete_thread(thread_id: str, user_id: str | None = Depends(get_user_id)):
    ok = await db.delete_thread(thread_id, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Thread not found")
    logger.info("Thread deleted thread_id=%s", thread_id)
    return {"ok": True}


@app.get("/api/threads/{thread_id}/messages", response_model=list[MessageOut])
async def get_messages(thread_id: str, user_id: str | None = Depends(get_user_id)):
    if not await db.thread_exists(thread_id, user_id=user_id):
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


async def _sse_chat(body: ChatRequest, user_id: str | None = None):
    logger.info(
        "POST /api/chat thread_id=%s regenerate=%s user_id=%s",
        body.thread_id,
        body.regenerate,
        user_id,
    )

    if not settings.openrouter_api_key:
        logger.error("OPENROUTER_API_KEY is not set")
        yield f"data: {json.dumps({'type': 'error', 'message': 'OPENROUTER_API_KEY is not set'})}\n\n"
        return

    if not await db.thread_exists(body.thread_id, user_id=user_id):
        logger.warning("Thread not found thread_id=%s", body.thread_id)
        yield f"data: {json.dumps({'type': 'error', 'message': 'Thread not found'})}\n\n"
        return

    if body.regenerate:
        logger.debug("Regenerate: deleting last assistant message thread_id=%s", body.thread_id)
        await db.delete_last_assistant_message(body.thread_id)
    else:
        await db.add_message(body.thread_id, "user", body.message)
        await db.maybe_set_thread_title_from_first_message(body.thread_id, body.message)

    rows = await db.get_messages(body.thread_id)
    if not rows:
        logger.warning("No messages found thread_id=%s", body.thread_id)
        yield f"data: {json.dumps({'type': 'error', 'message': 'No messages to continue from'})}\n\n"
        return
    if rows[-1]["role"] != "user":
        logger.warning(
            "Last message is not from user thread_id=%s last_role=%s",
            body.thread_id,
            rows[-1]["role"],
        )
        yield f"data: {json.dumps({'type': 'error', 'message': 'Last message must be from user to run the model'})}\n\n"
        return

    # Magic query: stream the canned demo response without calling the LLM.
    # Edit demo_response.py to customise what the demo shows.
    if rows[-1]["content"].strip() == "demo!":
        logger.info("Demo magic query detected thread_id=%s", body.thread_id)
        async for event in stream_demo():
            yield event
        return

    lc_messages = _rows_to_messages(rows)
    logger.debug("Loaded %d message(s) for graph thread_id=%s", len(lc_messages), body.thread_id)

    # Classify intent upfront and emit as a labeled reasoning event.
    # The "label" value controls the collapsible section heading in the UI.
    # Change "Query intent" below to rename that section.
    last_user_text = rows[-1]["content"] or ""
    try:
        intent_result = await asyncio.to_thread(classify_intent_text, last_user_text)
        intent = intent_result.intent
        logger.info("Pre-classification intent=%s thread_id=%s", intent, body.thread_id)
        yield f"data: {json.dumps({'type': 'reasoning', 'content': f'Intent: {intent}', 'label': 'Query intent'})}\n\n"
    except Exception as e:
        logger.warning("Pre-classification failed, defaulting to general: %s", e)
        intent = "general"

    graph = get_graph()
    full_reasoning = ""
    full_text = ""

    try:
        # stream_mode="messages" yields (AIMessageChunk | AIMessage, metadata dict)
        async for msg_chunk, _metadata in graph.astream(
            {"messages": lc_messages, "intent": ""},
            stream_mode="messages",
        ):
            _reasoning_preview = (
                (getattr(msg_chunk, "additional_kwargs", None) or {}).get("reasoning_content") or ""
            )[:60]
            logger.debug(
                "chunk node=%s content=%r blocks=%s reasoning=%r",
                _metadata.get("langgraph_node"),
                getattr(msg_chunk, "content", "")[:60],
                [b.get("type") for b in _extract_blocks(msg_chunk)],
                _reasoning_preview,
            )
            for block in _extract_blocks(msg_chunk):
                btype = block.get("type")
                if btype == "reasoning":
                    delta = block.get("reasoning") or ""
                    if delta:
                        full_reasoning += delta
                        # Change "Reasoning" below to rename the main agent thinking section.
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': delta, 'label': 'Reasoning'})}\n\n"
                elif btype == "text":
                    delta = block.get("text") or ""
                    if delta:
                        full_text += delta
                        yield f"data: {json.dumps({'type': 'token', 'content': delta})}\n\n"
                elif btype == "thinking":
                    delta = block.get("thinking") or ""
                    if delta:
                        full_reasoning += delta
                        # Change "Reasoning" below to rename the main agent thinking section.
                        yield f"data: {json.dumps({'type': 'reasoning', 'content': delta, 'label': 'Reasoning'})}\n\n"

        reasoning_to_store = full_reasoning.strip() or None
        logger.debug(
            "Stream complete thread_id=%s text_chars=%d reasoning_chars=%d",
            body.thread_id,
            len(full_text),
            len(full_reasoning),
        )
        await db.add_message(
            body.thread_id,
            "assistant",
            full_text,
            reasoning=reasoning_to_store,
        )
        logger.info("SSE stream complete thread_id=%s", body.thread_id)
    except Exception as e:
        err_msg = str(e).strip() or type(e).__name__
        logger.exception("Error during graph stream thread_id=%s: %s", body.thread_id, err_msg)
        yield f"data: {json.dumps({'type': 'error', 'message': err_msg})}\n\n"
    finally:
        yield f"data: {json.dumps({'type': 'done'})}\n\n"


@app.post("/api/chat")
async def chat(body: ChatRequest, user_id: str | None = Depends(get_user_id)):
    return StreamingResponse(
        _sse_chat(body, user_id=user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def create_app() -> FastAPI:
    return app
