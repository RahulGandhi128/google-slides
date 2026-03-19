"""
Chat sessions and messages - CRUD for chat history.
Saves user messages, assistant content, and plan JSON (no tool calls).
"""
import json
from datetime import datetime
from typing import Any

from sqlalchemy import text

from .connection import SessionLocal


def create_session(title: str = "New chat") -> int:
    """Create session (SQLite compatible)."""
    db = SessionLocal()
    try:
        now = datetime.utcnow().isoformat()
        db.execute(
            text("INSERT INTO chat_sessions (title, updated_at) VALUES (:title, :now)"),
            {"title": title, "now": now},
        )
        db.commit()
        return db.execute(text("SELECT last_insert_rowid()")).scalar()
    finally:
        db.close()


def create_session_if_needed(session_id: int | None) -> int:
    """Return session_id if valid, else create new session."""
    if session_id:
        db = SessionLocal()
        try:
            r = db.execute(text("SELECT id FROM chat_sessions WHERE id = :id"), {"id": session_id})
            if r.fetchone():
                return session_id
        finally:
            db.close()
    return create_session()


def update_session_title(session_id: int, title: str) -> None:
    """Update session title (e.g. from first user message)."""
    db = SessionLocal()
    try:
        db.execute(
            text(
                "UPDATE chat_sessions SET title = :title, updated_at = :now WHERE id = :id"
            ),
            {"id": session_id, "title": title[:100], "now": datetime.utcnow().isoformat()},
        )
        db.commit()
    finally:
        db.close()


def add_message(
    session_id: int,
    role: str,
    content: str,
    plan_json: str | None = None,
    mode: str | None = None,
) -> int:
    """Add a message. Returns message id. plan_json is stored for assistant plan messages only."""
    db = SessionLocal()
    try:
        db.execute(
            text(
                "INSERT INTO chat_messages (session_id, role, content, plan_json, mode) VALUES (:sid, :role, :content, :plan, :mode)"
            ),
            {
                "sid": session_id,
                "role": role,
                "content": content or "",
                "plan": plan_json,
                "mode": (mode or "agent"),
            },
        )
        db.execute(
            text("UPDATE chat_sessions SET updated_at = :now WHERE id = :id"),
            {"id": session_id, "now": datetime.utcnow().isoformat()},
        )
        db.commit()
        return db.execute(text("SELECT last_insert_rowid()")).scalar()
    finally:
        db.close()


def list_sessions(limit: int = 50, mode: str | None = None) -> list[dict[str, Any]]:
    """List chat sessions, most recent first. If mode is set, only return sessions with at least one message of that mode."""
    db = SessionLocal()
    try:
        if mode:
            r = db.execute(
                text(
                    """
                    SELECT DISTINCT s.id, s.title, s.created_at, s.updated_at
                    FROM chat_sessions s
                    LEFT JOIN chat_messages m ON m.session_id = s.id
                    WHERE m.mode = :mode
                    ORDER BY s.updated_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit, "mode": mode},
            )
        else:
            r = db.execute(
                text(
                    "SELECT id, title, created_at, updated_at FROM chat_sessions ORDER BY updated_at DESC LIMIT :limit"
                ),
                {"limit": limit},
            )
        rows = r.fetchall()
        return [
            {
                "id": row[0],
                "title": row[1] or "New chat",
                "createdAt": row[2],
                "updatedAt": row[3],
            }
            for row in rows
        ]
    finally:
        db.close()


def get_session_with_messages(session_id: int) -> dict[str, Any] | None:
    """Get a session and its messages. Returns None if not found."""
    db = SessionLocal()
    try:
        r = db.execute(
            text("SELECT id, title, created_at, updated_at FROM chat_sessions WHERE id = :id"),
            {"id": session_id},
        )
        row = r.fetchone()
        if not row:
            return None

        msgs = db.execute(
            text(
                "SELECT id, role, content, plan_json, mode, created_at FROM chat_messages WHERE session_id = :id ORDER BY id ASC"
            ),
            {"id": session_id},
        ).fetchall()

        messages = []
        for m in msgs:
            msg = {
                "id": m[0],
                "role": m[1],
                "content": m[2] or "",
                "createdAt": m[5],
            }
            if m[3]:
                try:
                    msg["plan"] = json.loads(m[3])
                    msg["hasPlan"] = True
                except json.JSONDecodeError:
                    pass
            if m[4]:
                msg["mode"] = m[4] or "agent"
            messages.append(msg)

        return {
            "id": row[0],
            "title": row[1] or "New chat",
            "createdAt": row[2],
            "updatedAt": row[3],
            "messages": messages,
        }
    finally:
        db.close()


def delete_session(session_id: int) -> bool:
    """Delete a session and its messages. Returns True if deleted."""
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM chat_messages WHERE session_id = :id"), {"id": session_id})
        r = db.execute(text("DELETE FROM chat_sessions WHERE id = :id"), {"id": session_id})
        db.commit()
        return r.rowcount > 0
    finally:
        db.close()
