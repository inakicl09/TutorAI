"""Study goals: one short goal text per student per grade+subject."""

from datetime import datetime, timezone
from typing import Optional

from tutorai import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_goal(student_username: str, grade: str, subject: str, goal_text: str) -> None:
    """Create or replace the goal for this student+grade+subject."""
    connection = db.get_connection()
    try:
        connection.execute(
            "INSERT INTO study_goals "
            "(student_username, grade, subject, goal_text, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(student_username, grade, subject) "
            "DO UPDATE SET goal_text = excluded.goal_text, "
            "              updated_at = excluded.updated_at",
            (student_username, grade, subject, goal_text, _now()),
        )
        connection.commit()
    finally:
        connection.close()


def get_goal(student_username: str, grade: str, subject: str) -> Optional[str]:
    """Return the goal text, or None if no goal has been set."""
    connection = db.get_connection()
    try:
        row = connection.execute(
            "SELECT goal_text FROM study_goals "
            "WHERE student_username = ? AND grade = ? AND subject = ?",
            (student_username, grade, subject),
        ).fetchone()
        return row["goal_text"] if row else None
    finally:
        connection.close()


def delete_goal(student_username: str, grade: str, subject: str) -> None:
    connection = db.get_connection()
    try:
        connection.execute(
            "DELETE FROM study_goals "
            "WHERE student_username = ? AND grade = ? AND subject = ?",
            (student_username, grade, subject),
        )
        connection.commit()
    finally:
        connection.close()
