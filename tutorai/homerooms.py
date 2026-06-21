"""Homerooms: students are split into grade-level groups capped at a
maximum size (e.g. "1º ESO - A", then "1º ESO - B" once "A" is full).
One student belongs to exactly one homeroom. Unrelated to the per-subject
classes in classes.py -- a homeroom is just an administrative grouping,
not tied to any teacher or subject.
"""

import string

from tutorai import db, subjects

MAX_STUDENTS_PER_HOMEROOM = 30


def _next_homeroom_letter(existing_names: list[str]) -> str:
    used_letters = {name.rsplit(" - ", 1)[-1] for name in existing_names}
    for letter in string.ascii_uppercase:
        if letter not in used_letters:
            return letter
    raise ValueError("Ran out of homeroom letters for this grade")


def assign_homeroom(grade: str) -> dict:
    """Return a homeroom for this grade with room to spare, creating a
    new one (the next letter) if all existing ones are full."""
    connection = db.get_connection()
    try:
        existing = connection.execute(
            "SELECT id, name FROM homerooms WHERE grade = ? ORDER BY name", (grade,)
        ).fetchall()

        for homeroom in existing:
            student_count = connection.execute(
                "SELECT COUNT(*) FROM users WHERE homeroom_id = ?", (homeroom["id"],)
            ).fetchone()[0]
            if student_count < MAX_STUDENTS_PER_HOMEROOM:
                return dict(homeroom)

        new_name = f"{grade} - {_next_homeroom_letter([row['name'] for row in existing])}"
        cursor = connection.execute(
            "INSERT INTO homerooms (name, grade) VALUES (?, ?)", (new_name, grade)
        )
        connection.commit()
        return {"id": cursor.lastrowid, "name": new_name, "grade": grade}
    finally:
        connection.close()


def list_homerooms(grade: str = None) -> list[dict]:
    """List homerooms, optionally filtered by grade, ordered by grade
    then name."""
    connection = db.get_connection()
    try:
        if grade:
            rows = connection.execute(
                "SELECT id, name, grade FROM homerooms WHERE grade = ?", (grade,)
            ).fetchall()
        else:
            rows = connection.execute("SELECT id, name, grade FROM homerooms").fetchall()
        result = [dict(row) for row in rows]
    finally:
        connection.close()

    grade_order = {g: i for i, g in enumerate(subjects.GRADES)}
    result.sort(key=lambda h: (grade_order.get(h["grade"], len(grade_order)), h["name"]))
    return result


def students_in_homeroom(homeroom_id: int) -> list[str]:
    """List student usernames in a homeroom, alphabetically."""
    connection = db.get_connection()
    try:
        rows = connection.execute(
            "SELECT username FROM users WHERE homeroom_id = ? ORDER BY username COLLATE NOCASE",
            (homeroom_id,),
        )
        return [row["username"] for row in rows]
    finally:
        connection.close()


def backfill_homerooms() -> None:
    """Place any student missing a homeroom into one for their grade
    (e.g. students created before this feature existed). Safe to call
    every startup, alongside db.init_db()."""
    connection = db.get_connection()
    try:
        students_missing_homeroom = connection.execute(
            "SELECT username, grade FROM users WHERE role = 'student' AND homeroom_id IS NULL"
        ).fetchall()
    finally:
        connection.close()

    for student in students_missing_homeroom:
        homeroom = assign_homeroom(student["grade"])
        connection = db.get_connection()
        try:
            connection.execute(
                "UPDATE users SET homeroom_id = ? WHERE username = ?",
                (homeroom["id"], student["username"]),
            )
            connection.commit()
        finally:
            connection.close()
