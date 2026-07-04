"""Question bank: teachers save individual questions here so Logos can
reference them when drafting a new test for the same grade+subject."""

from datetime import datetime, timezone
from typing import Optional

from tutorai import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_question(
    teacher_username: str,
    grade: str,
    subject: str,
    question_text: str,
    answer_text: str,
) -> None:
    connection = db.get_connection()
    try:
        connection.execute(
            "INSERT INTO question_bank "
            "(teacher_username, grade, subject, question_text, answer_text, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (teacher_username, grade, subject, question_text, answer_text, _now()),
        )
        connection.commit()
    finally:
        connection.close()


def list_questions_for_teacher(
    teacher_username: str,
    grade: Optional[str] = None,
    subject: Optional[str] = None,
) -> list[dict]:
    connection = db.get_connection()
    try:
        if grade and subject:
            rows = connection.execute(
                "SELECT * FROM question_bank "
                "WHERE teacher_username = ? AND grade = ? AND subject = ? "
                "ORDER BY id",
                (teacher_username, grade, subject),
            ).fetchall()
        elif grade:
            rows = connection.execute(
                "SELECT * FROM question_bank "
                "WHERE teacher_username = ? AND grade = ? ORDER BY id",
                (teacher_username, grade),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM question_bank WHERE teacher_username = ? ORDER BY id",
                (teacher_username,),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def delete_question(question_id: int, teacher_username: str) -> None:
    connection = db.get_connection()
    try:
        connection.execute(
            "DELETE FROM question_bank WHERE id = ? AND teacher_username = ?",
            (question_id, teacher_username),
        )
        connection.commit()
    finally:
        connection.close()
