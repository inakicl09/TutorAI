"""Teacher-assigned exercises that students can bring into a Socrates chat."""

from datetime import datetime, timezone

from tutorai import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_exercise(
    teacher_username: str,
    grade: str,
    subject: str,
    title: str,
    content: str,
) -> None:
    connection = db.get_connection()
    try:
        connection.execute(
            "INSERT INTO exercises "
            "(teacher_username, grade, subject, title, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (teacher_username, grade, subject, title, content, _now()),
        )
        connection.commit()
    finally:
        connection.close()


def list_exercises_for_teacher(teacher_username: str) -> list[dict]:
    connection = db.get_connection()
    try:
        rows = connection.execute(
            "SELECT * FROM exercises WHERE teacher_username = ? "
            "ORDER BY created_at DESC",
            (teacher_username,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def list_exercises_for_student(student_username: str) -> list[dict]:
    """Return exercises from teachers the student is linked to, for the
    exact (teacher, grade, subject) combos they're enrolled in."""
    connection = db.get_connection()
    try:
        rows = connection.execute(
            """
            SELECT e.*
            FROM exercises e
            INNER JOIN subject_links sl
                ON  e.teacher_username = sl.teacher_username
                AND e.grade            = sl.grade
                AND e.subject          = sl.subject
            WHERE sl.student_username = ?
            ORDER BY e.created_at DESC
            """,
            (student_username,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def delete_exercise(exercise_id: int, teacher_username: str) -> None:
    connection = db.get_connection()
    try:
        connection.execute(
            "DELETE FROM exercises WHERE id = ? AND teacher_username = ?",
            (exercise_id, teacher_username),
        )
        connection.commit()
    finally:
        connection.close()
