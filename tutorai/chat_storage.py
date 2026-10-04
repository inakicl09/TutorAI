"""Chat persistence in the shared SQLite database (see db.py): one row
per chat, one row per message, so chats survive restarting the app.
"""

from datetime import datetime, timezone
from typing import Optional

from tutorai import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_chat(
    username: str,
    grade: str,
    subject: str,
    system_prompt: str,
    created_at: Optional[str] = None,
    mode: Optional[str] = None,
) -> dict:
    """Start a new chat for this student and return it, system message
    included. `mode` is only meaningful for Logos chats ("draft" or
    "analyze") -- leave it None for Socrates/Artemis chats."""
    created_at = created_at or _now()
    connection = db.get_connection()
    try:
        cursor = connection.execute(
            "INSERT INTO chats (username, grade, subject, mode) VALUES (?, ?, ?, ?)",
            (username, grade, subject, mode),
        )
        chat_id = cursor.lastrowid
        connection.execute(
            "INSERT INTO chat_messages (chat_id, position, role, content, created_at) "
            "VALUES (?, 0, 'system', ?, ?)",
            (chat_id, system_prompt, created_at),
        )
        connection.commit()
        return {
            "id": chat_id,
            "grade": grade,
            "subject": subject,
            "mode": mode,
            "history": [{"role": "system", "content": system_prompt, "created_at": created_at}],
        }
    finally:
        connection.close()


def add_message(chat_id: int, role: str, content: str, created_at: Optional[str] = None) -> None:
    """Append one message to an existing chat."""
    created_at = created_at or _now()
    connection = db.get_connection()
    try:
        next_position = connection.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM chat_messages WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO chat_messages (chat_id, position, role, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (chat_id, next_position, role, content, created_at),
        )
        connection.commit()
    finally:
        connection.close()


def update_system_prompt(chat_id: int, system_prompt: str) -> None:
    """Replace a chat's stored system message (position 0) with a freshly
    built one. Called when a chat is opened so that edits to prompts.py
    apply to chats that already exist, not just newly created ones --
    otherwise a chat keeps forever the rules that were in place the day
    it was started."""
    connection = db.get_connection()
    try:
        connection.execute(
            "UPDATE chat_messages SET content = ? WHERE chat_id = ? AND position = 0",
            (system_prompt, chat_id),
        )
        connection.commit()
    finally:
        connection.close()


def delete_chat(chat_id: int, username: str) -> bool:
    """Delete one chat and all of its messages. `username` is who is asking:
    a chat that doesn't belong to them isn't deleted, and False is returned.
    """
    connection = db.get_connection()
    try:
        owner_row = connection.execute(
            "SELECT username FROM chats WHERE id = ?", (chat_id,)
        ).fetchone()
        if owner_row is None or owner_row["username"] != username:
            return False

        connection.execute("DELETE FROM chat_messages WHERE chat_id = ?", (chat_id,))
        connection.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        connection.commit()
        return True
    finally:
        connection.close()


def load_chats(username: str) -> list[dict]:
    """Return all of a student's chats, oldest first, each with its full
    message history."""
    connection = db.get_connection()
    try:
        chat_rows = connection.execute(
            "SELECT id, grade, subject, mode FROM chats WHERE username = ? ORDER BY id",
            (username,),
        ).fetchall()

        chats = []
        for chat_row in chat_rows:
            message_rows = connection.execute(
                "SELECT role, content, created_at FROM chat_messages "
                "WHERE chat_id = ? ORDER BY position",
                (chat_row["id"],),
            ).fetchall()
            chats.append(
                {
                    "id": chat_row["id"],
                    "grade": chat_row["grade"],
                    "subject": chat_row["subject"],
                    "mode": chat_row["mode"],
                    "history": [dict(row) for row in message_rows],
                }
            )
        return chats
    finally:
        connection.close()
