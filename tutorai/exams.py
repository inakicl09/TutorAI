"""Saved tests: a teacher's finished test/exam content, drafted by
chatting with Logos and saved once they're happy with it. Stored in the
shared SQLite database's `tests` table (see db.py) -- named exams.py
here, not tests.py, so it doesn't read like the project's pytest suite
(tests/, no __init__.py, just a sibling directory -- not an actual
import collision, but a human-confusion one).

Two flavors share the `tests` table:
- Freeform drafts (just `content`, from the open-ended Logos chat) --
  good for printing, not completable by students.
- Structured multiple-choice tests (`test_questions` rows, created via
  publish_test) -- these are what students see and complete, graded
  immediately and recorded in `test_submissions` (one attempt each).
"""

import re
from datetime import datetime, timezone
from typing import Optional

from tutorai import db, prompts

# Matches one QUESTION/A/B/C/D/CORRECT block from Logos's structured-test
# output (see prompts.build_structured_test_prompt). Local models don't
# always follow the format perfectly, so this is tolerant of stray
# whitespace, but still requires every field to be present.
_QUESTION_BLOCK_PATTERN = re.compile(
    r"QUESTION:\s*(?P<question>.+?)\s*"
    r"A\)\s*(?P<option_a>.+?)\s*"
    r"B\)\s*(?P<option_b>.+?)\s*"
    r"C\)\s*(?P<option_c>.+?)\s*"
    r"D\)\s*(?P<option_d>.+?)\s*"
    r"CORRECT:\s*(?P<correct>[ABCD])",
    re.DOTALL | re.IGNORECASE,
)


def save_test(teacher_username: str, grade: str, subject: str, title: str, content: str) -> int:
    """Save a freeform test draft and return its id."""
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
    """Return a teacher's saved freeform tests, newest first."""
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
    """Delete a test (freeform or published), but only if it belongs to
    this teacher. Also removes its questions and any submissions."""
    connection = db.get_connection()
    try:
        owned = connection.execute(
            "SELECT 1 FROM tests WHERE id = ? AND teacher_username = ?",
            (test_id, teacher_username),
        ).fetchone()
        if owned is None:
            return

        connection.execute("DELETE FROM test_submissions WHERE test_id = ?", (test_id,))
        connection.execute("DELETE FROM test_questions WHERE test_id = ?", (test_id,))
        connection.execute(
            "DELETE FROM tests WHERE id = ? AND teacher_username = ?",
            (test_id, teacher_username),
        )
        connection.commit()
    finally:
        connection.close()


def parse_structured_test(raw_text: str) -> list[dict]:
    """Parse Logos's structured-test output into a list of question
    dicts. Returns an empty list if nothing parseable is found -- local
    models don't always follow the format perfectly, so callers should
    treat an empty result as "ask the teacher to regenerate" rather than
    crash."""
    questions = []
    for block in raw_text.split(prompts.QUESTION_SEPARATOR):
        match = _QUESTION_BLOCK_PATTERN.search(block)
        if not match:
            continue
        questions.append(
            {
                "question_text": match["question"].strip(),
                "option_a": match["option_a"].strip(),
                "option_b": match["option_b"].strip(),
                "option_c": match["option_c"].strip(),
                "option_d": match["option_d"].strip(),
                "correct_option": match["correct"].strip().upper(),
            }
        )
    return questions


def publish_test(
    teacher_username: str, grade: str, subject: str, title: str, questions: list[dict]
) -> int:
    """Save a structured test with its questions and publish it
    immediately -- visible to every student linked to this teacher for
    this grade+subject. Returns the new test's id."""
    connection = db.get_connection()
    try:
        cursor = connection.execute(
            "INSERT INTO tests (teacher_username, grade, subject, title, published_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (teacher_username, grade, subject, title, datetime.now(timezone.utc).isoformat()),
        )
        test_id = cursor.lastrowid
        for position, question in enumerate(questions):
            connection.execute(
                "INSERT INTO test_questions (test_id, position, question_text, "
                "option_a, option_b, option_c, option_d, correct_option) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    test_id,
                    position,
                    question["question_text"],
                    question["option_a"],
                    question["option_b"],
                    question["option_c"],
                    question["option_d"],
                    question["correct_option"],
                ),
            )
        connection.commit()
        return test_id
    finally:
        connection.close()


def get_test_questions(test_id: int) -> list[dict]:
    """Return a published test's questions in order."""
    connection = db.get_connection()
    try:
        rows = connection.execute(
            "SELECT id, question_text, option_a, option_b, option_c, option_d, "
            "correct_option FROM test_questions WHERE test_id = ? ORDER BY position",
            (test_id,),
        )
        return [dict(row) for row in rows]
    finally:
        connection.close()


def list_published_tests_for_teacher(teacher_username: str) -> list[dict]:
    """Return a teacher's published (structured) tests, newest first."""
    connection = db.get_connection()
    try:
        rows = connection.execute(
            "SELECT id, grade, subject, title, published_at FROM tests "
            "WHERE teacher_username = ? AND published_at IS NOT NULL ORDER BY id DESC",
            (teacher_username,),
        )
        return [dict(row) for row in rows]
    finally:
        connection.close()


def list_submissions(test_id: int) -> list[dict]:
    """Return every student's submission for a test."""
    connection = db.get_connection()
    try:
        rows = connection.execute(
            "SELECT student_username, score, total, submitted_at FROM test_submissions "
            "WHERE test_id = ?",
            (test_id,),
        )
        return [dict(row) for row in rows]
    finally:
        connection.close()


def list_published_tests_for_student(student_username: str) -> list[dict]:
    """Return every published test for a grade+subject the student is
    linked to a teacher for."""
    connection = db.get_connection()
    try:
        rows = connection.execute(
            "SELECT DISTINCT tests.id, tests.teacher_username, tests.grade, "
            "tests.subject, tests.title FROM tests "
            "JOIN subject_links ON subject_links.teacher_username = tests.teacher_username "
            "AND subject_links.grade = tests.grade AND subject_links.subject = tests.subject "
            "WHERE subject_links.student_username = ? AND tests.published_at IS NOT NULL",
            (student_username,),
        )
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_submission(test_id: int, student_username: str) -> Optional[dict]:
    """Return a student's submission for a test, or None if they haven't
    completed it yet."""
    connection = db.get_connection()
    try:
        row = connection.execute(
            "SELECT score, total, submitted_at FROM test_submissions "
            "WHERE test_id = ? AND student_username = ?",
            (test_id, student_username),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def submit_test(test_id: int, student_username: str, answers: dict) -> dict:
    """Grade a student's answers (question_id -> selected letter) against
    the test's correct options, store the one allowed attempt, and
    return {"score": ..., "total": ...}. Raises ValueError if the student
    already completed this test."""
    if get_submission(test_id, student_username) is not None:
        raise ValueError("Student already submitted this test")

    questions = get_test_questions(test_id)
    total = len(questions)
    score = sum(
        1
        for question in questions
        if answers.get(question["id"]) == question["correct_option"]
    )

    connection = db.get_connection()
    try:
        connection.execute(
            "INSERT INTO test_submissions (test_id, student_username, submitted_at, score, total) "
            "VALUES (?, ?, ?, ?, ?)",
            (test_id, student_username, datetime.now(timezone.utc).isoformat(), score, total),
        )
        connection.commit()
    finally:
        connection.close()

    return {"score": score, "total": total}
