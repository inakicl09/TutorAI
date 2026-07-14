"""Notes a student saves from assistant messages in chat (see db.py)."""

from datetime import datetime, timezone
from typing import Optional

from tutorai import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_note(student_username: str, grade: str, subject: str, content: str) -> None:
    connection = db.get_connection()
    try:
        connection.execute(
            "INSERT INTO notes (student_username, grade, subject, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (student_username, grade, subject, content, _now()),
        )
        connection.commit()
    finally:
        connection.close()


def list_notes_for_student(
    student_username: str,
    subject: Optional[str] = None,
) -> list[dict]:
    connection = db.get_connection()
    try:
        if subject:
            rows = connection.execute(
                "SELECT * FROM notes WHERE student_username = ? AND subject = ? "
                "ORDER BY created_at DESC",
                (student_username, subject),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM notes WHERE student_username = ? ORDER BY created_at DESC",
                (student_username,),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def delete_note(note_id: int, student_username: str) -> None:
    connection = db.get_connection()
    try:
        connection.execute(
            "DELETE FROM notes WHERE id = ? AND student_username = ?",
            (note_id, student_username),
        )
        connection.commit()
    finally:
        connection.close()
