"""SQLite persistence for threads and messages."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from assistant_service.config import settings

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


async def init_db(db_path: Path | None = None) -> None:
    path = db_path or settings.assistant_db_path
    logger.debug("init_db: path=%s", path)
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS threads (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New chat',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                reasoning TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
            )
            """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id)"
        )
        await db.commit()


async def create_thread(
    title: str = "New chat",
    thread_id: str | None = None,
    db_path: Path | None = None,
) -> str:
    path = db_path or settings.assistant_db_path
    tid = thread_id or str(uuid.uuid4())
    now = _utc_now()
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "INSERT INTO threads (id, title, created_at, updated_at, archived) VALUES (?, ?, ?, ?, 0)",
            (tid, title, now, now),
        )
        await db.commit()
    logger.debug("create_thread: thread_id=%s title=%r", tid, title)
    return tid


async def list_threads(
    q: str | None = None,
    *,
    include_archived: bool = False,
    db_path: Path | None = None,
) -> list[dict]:
    path = db_path or settings.assistant_db_path
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        archived_clause = "" if include_archived else "AND archived = 0"
        if q:
            like = f"%{q}%"
            cursor = await db.execute(
                f"""
                SELECT id, title, updated_at, archived FROM threads
                WHERE (title LIKE ? OR id LIKE ?) {archived_clause}
                ORDER BY updated_at DESC
                """,
                (like, like),
            )
        else:
            cursor = await db.execute(
                f"""
                SELECT id, title, updated_at, archived FROM threads
                WHERE 1=1 {archived_clause}
                ORDER BY updated_at DESC
                """
            )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_thread(thread_id: str, db_path: Path | None = None) -> dict | None:
    path = db_path or settings.assistant_db_path
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, title, updated_at, archived FROM threads WHERE id = ?",
            (thread_id,),
        )
        row = await cursor.fetchone()
    return dict(row) if row else None


async def rename_thread(thread_id: str, title: str, db_path: Path | None = None) -> bool:
    path = db_path or settings.assistant_db_path
    now = _utc_now()
    async with aiosqlite.connect(path) as db:
        cur = await db.execute(
            "UPDATE threads SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, thread_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def patch_thread(
    thread_id: str,
    *,
    title: str | None = None,
    archived: bool | None = None,
    db_path: Path | None = None,
) -> bool:
    path = db_path or settings.assistant_db_path
    now = _utc_now()
    fields: list[str] = []
    values: list = []
    if title is not None:
        fields.append("title = ?")
        values.append(title)
    if archived is not None:
        fields.append("archived = ?")
        values.append(1 if archived else 0)
    if not fields:
        return await thread_exists(thread_id, db_path)
    fields.append("updated_at = ?")
    values.append(now)
    values.append(thread_id)
    async with aiosqlite.connect(path) as db:
        cur = await db.execute(
            f"UPDATE threads SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_thread(thread_id: str, db_path: Path | None = None) -> bool:
    path = db_path or settings.assistant_db_path
    async with aiosqlite.connect(path) as db:
        await db.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
        cur = await db.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
        await db.commit()
        return cur.rowcount > 0


async def add_message(
    thread_id: str,
    role: str,
    content: str,
    reasoning: str | None = None,
    db_path: Path | None = None,
) -> str:
    path = db_path or settings.assistant_db_path
    mid = str(uuid.uuid4())
    now = _utc_now()
    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            INSERT INTO messages (id, thread_id, role, content, reasoning, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (mid, thread_id, role, content, reasoning, now),
        )
        await db.execute(
            "UPDATE threads SET updated_at = ? WHERE id = ?",
            (now, thread_id),
        )
        await db.commit()
    logger.debug(
        "add_message: thread_id=%s role=%s content_chars=%d has_reasoning=%s",
        thread_id,
        role,
        len(content),
        reasoning is not None,
    )
    return mid


async def delete_last_assistant_message(thread_id: str, db_path: Path | None = None) -> bool:
    """Remove the most recent assistant message (for regenerate/retry). Returns whether a row was deleted."""
    path = db_path or settings.assistant_db_path
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT id FROM messages
            WHERE thread_id = ? AND role = 'assistant'
            ORDER BY created_at DESC LIMIT 1
            """,
            (thread_id,),
        )
        row = await cur.fetchone()
        if not row:
            logger.debug("delete_last_assistant_message: no assistant message found thread_id=%s", thread_id)
            return False
        mid = row["id"]
        await db.execute("DELETE FROM messages WHERE id = ?", (mid,))
        await db.execute(
            "UPDATE threads SET updated_at = ? WHERE id = ?",
            (_utc_now(), thread_id),
        )
        await db.commit()
    logger.debug("delete_last_assistant_message: deleted message_id=%s thread_id=%s", mid, thread_id)
    return True


async def get_messages(thread_id: str, db_path: Path | None = None) -> list[dict]:
    path = db_path or settings.assistant_db_path
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, role, content, reasoning, created_at FROM messages
            WHERE thread_id = ?
            ORDER BY created_at ASC
            """,
            (thread_id,),
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def thread_exists(thread_id: str, db_path: Path | None = None) -> bool:
    path = db_path or settings.assistant_db_path
    async with aiosqlite.connect(path) as db:
        cursor = await db.execute("SELECT 1 FROM threads WHERE id = ?", (thread_id,))
        row = await cursor.fetchone()
    return row is not None


async def maybe_set_thread_title_from_first_message(
    thread_id: str,
    user_text: str,
    db_path: Path | None = None,
) -> None:
    """If thread still has default title 'New chat', set a short title from first user message."""
    path = db_path or settings.assistant_db_path
    snippet = (user_text.strip()[:60] + "…") if len(user_text.strip()) > 60 else user_text.strip()
    if not snippet:
        return
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT title FROM threads WHERE id = ?",
            (thread_id,),
        )
        row = await cur.fetchone()
        if not row or row["title"] != "New chat":
            return
        await db.execute(
            "UPDATE threads SET title = ?, updated_at = ? WHERE id = ?",
            (snippet, _utc_now(), thread_id),
        )
        await db.commit()