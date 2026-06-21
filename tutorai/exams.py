"""Saved tests: a teacher's finished test/exam content, drafted by
chatting with Logos (see chat.ask_logos) and saved once they're happy
with it. Stored in the shared SQLite database's `tests` table (see
db.py) -- named exams.py here, not tests.py, so it doesn't read like the
project's pytest test suite.
"""

from tutorai import db


def save_test(teacher_username: str, grade: str, subject: str, title: str, content: str) -> int:
    """Save a test and return its id."""
    connection = db.get_connection()
    try:
        cursor = connection.execute(
            "INSERT INTO tests (teacher_username, grade, subject, title, content) "
            "VALUES (?, ?, ?, ?, ?)",
            (teacher_username, grade, subject, title, content),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def list_tests_for_teacher(teacher_username: str) -> list[dict]:
    """Return a teacher's saved tests, newest first."""
    connection = db.get_connection()
    try:
        rows = connection.execute(
            "SELECT id, grade, subject, title, content FROM tests "
            "WHERE teacher_username = ? ORDER BY id DESC",
            (teacher_username,),
        )
        return [dict(row) for row in rows]
    finally:
        connection.close()


def delete_test(test_id: int, teacher_username: str) -> None:
    """Delete a test, but only if it belongs to this teacher."""
    connection = db.get_connection()
    try:
        connection.execute(
            "DELETE FROM tests WHERE id = ? AND teacher_username = ?",
            (test_id, teacher_username),
        )
        connection.commit()
    finally:
        connection.close()
