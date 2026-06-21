"""Classes: each one is a teacher's group for a specific grade+subject
(e.g. "Matemáticas - 3º ESO" taught by profesor_lopez). A teacher who
teaches several grade+subject combos teaches that many classes. A
student is "in" a class once they're linked to that teacher for that
grade and subject (see users.link_student_to_teacher) -- there's no
separate enrollment table, since a class and a subject_link describe the
same (teacher, grade, subject) relationship.

Unrelated to homerooms.py, which groups students by grade only.
"""

from tutorai import db, subjects


def get_or_create_class(teacher_username: str, grade: str, subject: str) -> dict:
    """Return the class for this teacher+grade+subject, creating it
    (and naming it) if it doesn't exist yet."""
    connection = db.get_connection()
    try:
        row = connection.execute(
            "SELECT id, name, teacher_username, grade, subject FROM classes "
            "WHERE teacher_username = ? AND grade = ? AND subject = ?",
            (teacher_username, grade, subject),
        ).fetchone()
        if row is not None:
            return dict(row)

        name = f"{subject} - {grade} ({teacher_username})"
        cursor = connection.execute(
            "INSERT INTO classes (name, teacher_username, grade, subject) "
            "VALUES (?, ?, ?, ?)",
            (name, teacher_username, grade, subject),
        )
        connection.commit()
        return {
            "id": cursor.lastrowid,
            "name": name,
            "teacher_username": teacher_username,
            "grade": grade,
            "subject": subject,
        }
    finally:
        connection.close()


def sync_with_teaching_assignments() -> None:
    """Make sure every existing teaching assignment has a matching class.
    Safe to call every startup, alongside db.init_db()."""
    connection = db.get_connection()
    try:
        assignments = connection.execute(
            "SELECT teacher_username, grade, subject FROM teaching_assignments"
        ).fetchall()
    finally:
        connection.close()

    for assignment in assignments:
        get_or_create_class(
            assignment["teacher_username"], assignment["grade"], assignment["subject"]
        )


def list_classes(grade: str = None, search_text: str = "") -> list[dict]:
    """List classes, optionally filtered by grade and/or a search term
    matched against the teacher's username, ordered by grade then
    subject."""
    connection = db.get_connection()
    try:
        query = (
            "SELECT id, name, teacher_username, grade, subject FROM classes "
            "WHERE teacher_username LIKE ?"
        )
        params = [f"%{search_text}%"]
        if grade:
            query += " AND grade = ?"
            params.append(grade)
        rows = [dict(row) for row in connection.execute(query, params)]
    finally:
        connection.close()

    grade_order = {g: i for i, g in enumerate(subjects.GRADES)}
    rows.sort(key=lambda c: (grade_order.get(c["grade"], len(grade_order)), c["subject"]))
    return rows


def students_in_class(class_id: int) -> list[str]:
    """List student usernames linked to this class's teacher for this
    class's grade+subject, alphabetically."""
    connection = db.get_connection()
    try:
        class_row = connection.execute(
            "SELECT teacher_username, grade, subject FROM classes WHERE id = ?", (class_id,)
        ).fetchone()
        if class_row is None:
            return []

        rows = connection.execute(
            "SELECT student_username FROM subject_links "
            "WHERE teacher_username = ? AND grade = ? AND subject = ? "
            "ORDER BY student_username COLLATE NOCASE",
            (class_row["teacher_username"], class_row["grade"], class_row["subject"]),
        )
        return [row["student_username"] for row in rows]
    finally:
        connection.close()


def classes_for_student(student_username: str) -> list[dict]:
    """List the classes a student is linked to, via their subject_links."""
    connection = db.get_connection()
    try:
        rows = connection.execute(
            "SELECT classes.id, classes.name, classes.teacher_username, "
            "classes.grade, classes.subject FROM subject_links "
            "JOIN classes ON classes.teacher_username = subject_links.teacher_username "
            "AND classes.grade = subject_links.grade "
            "AND classes.subject = subject_links.subject "
            "WHERE subject_links.student_username = ?",
            (student_username,),
        )
        return [dict(row) for row in rows]
    finally:
        connection.close()
