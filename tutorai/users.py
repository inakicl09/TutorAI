"""User accounts: signup and login, stored in the shared SQLite database
(see db.py).

Three account types:
- "student": has a home grade and a list of subject links, each one
  pointing at the teacher who gave them access to that grade+subject.
  This is what lets a student retake a subject at a lower grade, as long
  as a teacher for that grade+subject has linked them.
- "teacher": has a list of (grade, subject) pairs they teach, and a join
  code students can use to link to them instead of searching.
- "admin": a single account, pre-seeded by create_admin.py. There is no
  signup path for admin accounts in the app itself.

Passwords are never stored in plain text. Each one is hashed with a
random salt using hashlib's PBKDF2 implementation (standard library).
"""

import hashlib
import secrets
import string
from typing import Optional

from tutorai import db

PBKDF2_ITERATIONS = 200_000
JOIN_CODE_LENGTH = 6
JOIN_CODE_CHARACTERS = string.ascii_uppercase + string.digits


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    ).hex()


def _generate_join_code(connection) -> str:
    """Generate a join code that isn't already used by another teacher."""
    while True:
        code = "".join(secrets.choice(JOIN_CODE_CHARACTERS) for _ in range(JOIN_CODE_LENGTH))
        existing = connection.execute(
            "SELECT 1 FROM users WHERE join_code = ?", (code,)
        ).fetchone()
        if existing is None:
            return code


def username_exists(username: str) -> bool:
    connection = db.get_connection()
    try:
        row = connection.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone()
        return row is not None
    finally:
        connection.close()


def get_user(username: str) -> Optional[dict]:
    """Return a user's full record, including their teaching assignments
    (if a teacher) or subject links (if a student), or None if unknown."""
    connection = db.get_connection()
    try:
        user_row = connection.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user_row is None:
            return None

        user = dict(user_row)
        user["teaching"] = [
            dict(row)
            for row in connection.execute(
                "SELECT grade, subject FROM teaching_assignments "
                "WHERE teacher_username = ?",
                (username,),
            )
        ]
        user["subject_links"] = [
            dict(row)
            for row in connection.execute(
                "SELECT grade, subject, teacher_username AS teacher FROM subject_links "
                "WHERE student_username = ?",
                (username,),
            )
        ]
        return user
    finally:
        connection.close()


def verify_login(username: str, password: str) -> bool:
    """Check a username/password pair against the stored accounts."""
    user = get_user(username)
    if user is None:
        return False

    return _hash_password(password, user["salt"]) == user["password_hash"]


def create_student(username: str, password: str, grade: str) -> None:
    """Add a new student account. Raises ValueError if the username is
    already taken."""
    connection = db.get_connection()
    try:
        if connection.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone():
            raise ValueError("Username already exists")

        salt = secrets.token_hex(16)
        connection.execute(
            "INSERT INTO users (username, role, salt, password_hash, grade) "
            "VALUES (?, 'student', ?, ?, ?)",
            (username, salt, _hash_password(password, salt), grade),
        )
        connection.commit()
    finally:
        connection.close()


def create_teacher(username: str, password: str) -> str:
    """Add a new teacher account and return their join code.

    Raises ValueError if the username is already taken.
    """
    connection = db.get_connection()
    try:
        if connection.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone():
            raise ValueError("Username already exists")

        salt = secrets.token_hex(16)
        join_code = _generate_join_code(connection)
        connection.execute(
            "INSERT INTO users (username, role, salt, password_hash, join_code) "
            "VALUES (?, 'teacher', ?, ?, ?)",
            (username, salt, _hash_password(password, salt), join_code),
        )
        connection.commit()
        return join_code
    finally:
        connection.close()


def create_admin(username: str, password: str) -> None:
    """Add the admin account.

    Meant to be run once via create_admin.py, not exposed in the app's
    signup form.
    """
    connection = db.get_connection()
    try:
        if connection.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone():
            raise ValueError("Username already exists")

        salt = secrets.token_hex(16)
        connection.execute(
            "INSERT INTO users (username, role, salt, password_hash) "
            "VALUES (?, 'admin', ?, ?)",
            (username, salt, _hash_password(password, salt)),
        )
        connection.commit()
    finally:
        connection.close()


def add_teaching_assignment(teacher_username: str, grade: str, subject: str) -> None:
    """Add a (grade, subject) pair to a teacher's teaching list."""
    connection = db.get_connection()
    try:
        connection.execute(
            "INSERT OR IGNORE INTO teaching_assignments "
            "(teacher_username, grade, subject) VALUES (?, ?, ?)",
            (teacher_username, grade, subject),
        )
        connection.commit()
    finally:
        connection.close()


def find_teachers(search_text: str = "") -> list[str]:
    """List teacher usernames in alphabetical order, optionally filtered
    by a search term."""
    connection = db.get_connection()
    try:
        rows = connection.execute(
            "SELECT username FROM users WHERE role = 'teacher' AND username LIKE ? "
            "ORDER BY username COLLATE NOCASE",
            (f"%{search_text}%",),
        )
        return [row["username"] for row in rows]
    finally:
        connection.close()


def find_teacher_by_join_code(join_code: str) -> Optional[str]:
    """Return the teacher's username for a join code, or None if unknown."""
    connection = db.get_connection()
    try:
        row = connection.execute(
            "SELECT username FROM users WHERE role = 'teacher' AND join_code = ?",
            (join_code,),
        ).fetchone()
        return row["username"] if row else None
    finally:
        connection.close()


def link_student_to_teacher(
    student_username: str, teacher_username: str, grade: str, subject: str
) -> None:
    """Give a student access to a grade+subject through a specific teacher.

    Raises ValueError if that teacher doesn't actually teach that
    grade+subject.
    """
    connection = db.get_connection()
    try:
        taught = connection.execute(
            "SELECT 1 FROM teaching_assignments "
            "WHERE teacher_username = ? AND grade = ? AND subject = ?",
            (teacher_username, grade, subject),
        ).fetchone()
        if taught is None:
            raise ValueError("That teacher doesn't teach that grade and subject")

        connection.execute(
            "INSERT OR IGNORE INTO subject_links "
            "(student_username, teacher_username, grade, subject) VALUES (?, ?, ?, ?)",
            (student_username, teacher_username, grade, subject),
        )
        connection.commit()
    finally:
        connection.close()


def unlink_student_from_teacher(
    student_username: str, teacher_username: str, grade: str, subject: str
) -> None:
    """Remove a student's access to a grade+subject through a specific
    teacher. Used by the admin dashboard."""
    connection = db.get_connection()
    try:
        connection.execute(
            "DELETE FROM subject_links WHERE student_username = ? "
            "AND teacher_username = ? AND grade = ? AND subject = ?",
            (student_username, teacher_username, grade, subject),
        )
        connection.commit()
    finally:
        connection.close()


def students_linked_to_teacher(teacher_username: str) -> list[str]:
    """List student usernames linked to this teacher for any subject."""
    connection = db.get_connection()
    try:
        rows = connection.execute(
            "SELECT DISTINCT student_username FROM subject_links "
            "WHERE teacher_username = ?",
            (teacher_username,),
        )
        return [row["student_username"] for row in rows]
    finally:
        connection.close()


def list_all_users(search_text: str = "") -> list[dict]:
    """Return every user's basic info (no password data) in alphabetical
    order, optionally filtered by a search term. For the admin
    dashboard."""
    connection = db.get_connection()
    try:
        rows = connection.execute(
            "SELECT username, role, grade, join_code FROM users WHERE username LIKE ? "
            "ORDER BY username COLLATE NOCASE",
            (f"%{search_text}%",),
        )
        return [dict(row) for row in rows]
    finally:
        connection.close()


def set_password(username: str, new_password: str) -> None:
    """Reset a user's password. Raises ValueError if the username is
    unknown. Used by the admin dashboard, since there's no self-service
    password recovery yet."""
    connection = db.get_connection()
    try:
        if connection.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone() is None:
            raise ValueError("Username does not exist")

        salt = secrets.token_hex(16)
        connection.execute(
            "UPDATE users SET salt = ?, password_hash = ? WHERE username = ?",
            (salt, _hash_password(new_password, salt), username),
        )
        connection.commit()
    finally:
        connection.close()


def regenerate_join_code(teacher_username: str) -> str:
    """Replace a teacher's join code with a new one and return it.
    Raises ValueError if the username isn't a teacher."""
    connection = db.get_connection()
    try:
        row = connection.execute(
            "SELECT role FROM users WHERE username = ?", (teacher_username,)
        ).fetchone()
        if row is None or row["role"] != "teacher":
            raise ValueError("Not a teacher account")

        new_code = _generate_join_code(connection)
        connection.execute(
            "UPDATE users SET join_code = ? WHERE username = ?",
            (new_code, teacher_username),
        )
        connection.commit()
        return new_code
    finally:
        connection.close()


def delete_user(username: str) -> None:
    """Delete a user account and everything that references it (their
    chats, teaching assignments, and subject links in either direction).
    Raises ValueError if the username is unknown.

    Used by the admin dashboard. There's no role branching here: each
    DELETE only matches rows that actually exist for this user's role, so
    it's safe to run all of them regardless of whether the account is a
    student, a teacher, or an admin.
    """
    connection = db.get_connection()
    try:
        if connection.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone() is None:
            raise ValueError("Username does not exist")

        chat_ids = [
            row["id"]
            for row in connection.execute(
                "SELECT id FROM chats WHERE username = ?", (username,)
            )
        ]
        for chat_id in chat_ids:
            connection.execute("DELETE FROM chat_messages WHERE chat_id = ?", (chat_id,))
        connection.execute("DELETE FROM chats WHERE username = ?", (username,))

        connection.execute(
            "DELETE FROM subject_links WHERE student_username = ? OR teacher_username = ?",
            (username, username),
        )
        connection.execute(
            "DELETE FROM teaching_assignments WHERE teacher_username = ?", (username,)
        )
        connection.execute("DELETE FROM tests WHERE teacher_username = ?", (username,))
        connection.execute("DELETE FROM users WHERE username = ?", (username,))
        connection.commit()
    finally:
        connection.close()
