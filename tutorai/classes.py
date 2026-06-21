"""Classes: one classroom group per grade (e.g. "1º ESO - A"). For now
there's exactly one class per grade, but it's a real table so more can be
added later (e.g. a second class for a crowded grade) without changing
how students or admins reference a class.
"""

from tutorai import db, subjects


def ensure_default_classes() -> None:
    """Create one class per grade if it doesn't already exist, and place
    any student missing a class into the one matching their grade (e.g.
    students created before this feature existed). Safe to call every
    startup, alongside db.init_db()."""
    connection = db.get_connection()
    try:
        for grade in subjects.GRADES:
            connection.execute(
                "INSERT OR IGNORE INTO classes (name, grade) VALUES (?, ?)",
                (f"{grade} - A", grade),
            )

        students_missing_class = connection.execute(
            "SELECT username, grade FROM users WHERE role = 'student' AND class_id IS NULL"
        ).fetchall()
        for student in students_missing_class:
            class_row = connection.execute(
                "SELECT id FROM classes WHERE grade = ?", (student["grade"],)
            ).fetchone()
            if class_row is not None:
                connection.execute(
                    "UPDATE users SET class_id = ? WHERE username = ?",
                    (class_row["id"], student["username"]),
                )

        connection.commit()
    finally:
        connection.close()


def get_class_for_grade(grade: str) -> dict:
    """Return the (currently only) class for a grade."""
    connection = db.get_connection()
    try:
        row = connection.execute(
            "SELECT id, name, grade FROM classes WHERE grade = ?", (grade,)
        ).fetchone()
        return dict(row)
    finally:
        connection.close()


def list_classes() -> list[dict]:
    """Return all classes, ordered the same way as subjects.GRADES."""
    connection = db.get_connection()
    try:
        rows = [dict(row) for row in connection.execute("SELECT id, name, grade FROM classes")]
    finally:
        connection.close()

    grade_order = {grade: index for index, grade in enumerate(subjects.GRADES)}
    rows.sort(key=lambda class_record: grade_order.get(class_record["grade"], len(grade_order)))
    return rows


def students_in_class(class_id: int) -> list[str]:
    """List student usernames in a class, alphabetically."""
    connection = db.get_connection()
    try:
        rows = connection.execute(
            "SELECT username FROM users WHERE class_id = ? ORDER BY username COLLATE NOCASE",
            (class_id,),
        )
        return [row["username"] for row in rows]
    finally:
        connection.close()
