"""Teacher announcements posted to a class, visible to all linked students."""

from datetime import datetime, timezone

from tutorai import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_announcement(
    teacher_username: str, grade: str, subject: str, content: str
) -> None:
    connection = db.get_connection()
    try:
        connection.execute(
            "INSERT INTO announcements "
            "(teacher_username, grade, subject, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (teacher_username, grade, subject, content, _now()),
        )
        connection.commit()
    finally:
        connection.close()


def list_announcements_for_teacher(teacher_username: str) -> list[dict]:
    connection = db.get_connection()
    try:
        rows = connection.execute(
            "SELECT * FROM announcements WHERE teacher_username = ? "
            "ORDER BY created_at DESC",
            (teacher_username,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def list_announcements_for_student(student_username: str) -> list[dict]:
    """Return all announcements from teachers the student is linked to,
    for the exact (teacher, grade, subject) combos they're enrolled in."""
    connection = db.get_connection()
    try:
        rows = connection.execute(
            """
            SELECT a.*, sl.teacher_username AS teacher
            FROM announcements a
            INNER JOIN subject_links sl
                ON  a.teacher_username = sl.teacher_username
                AND a.grade            = sl.grade
                AND a.subject          = sl.subject
            WHERE sl.student_username = ?
            ORDER BY a.created_at DESC
            """,
            (student_username,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def delete_announcement(announcement_id: int, teacher_username: str) -> None:
    connection = db.get_connection()
    try:
        connection.execute(
            "DELETE FROM announcements WHERE id = ? AND teacher_username = ?",
            (announcement_id, teacher_username),
        )
        connection.commit()
    finally:
        connection.close()
