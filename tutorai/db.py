"""Single SQLite database for TutorAI: users, chats, and (eventually)
tests. Centralized here so every module talks to the same schema.

Two distinct "class" concepts live here, on purpose:
- `classes`: a teacher's group for one grade+subject (e.g. "Matemáticas
  3º ESO with profesor_lopez"). See classes.py.
- `homerooms`: a grade-level administrative group capped at a maximum
  size (e.g. "3º ESO - A", "3º ESO - B"). See homerooms.py.
"""

import os
import sqlite3

from tutorai import config


def get_connection() -> sqlite3.Connection:
    """Open a connection to the database, creating its folder if needed."""
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    connection = sqlite3.connect(config.DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    """Create all tables if they don't exist yet. Safe to call every time
    the app starts."""
    connection = get_connection()
    try:
        # Migration: "classes" used to mean "one homeroom per grade"
        # (id, name, grade). That's now called "homerooms" -- the table
        # is simply renamed, since its old shape matches exactly what
        # homerooms need. The new "classes" table means something
        # different (a teacher's grade+subject group) and gets created
        # fresh below.
        existing_tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        if "classes" in existing_tables and "homerooms" not in existing_tables:
            existing_class_columns = [
                row["name"] for row in connection.execute("PRAGMA table_info(classes)")
            ]
            if "teacher_username" not in existing_class_columns:
                connection.execute("ALTER TABLE classes RENAME TO homerooms")

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                encrypted_password TEXT,
                grade TEXT,
                join_code TEXT UNIQUE,
                homeroom_id INTEGER REFERENCES homerooms(id)
            );

            -- A grade-level administrative group, capped at a maximum
            -- size (homerooms.MAX_STUDENTS_PER_HOMEROOM). Every student
            -- belongs to exactly one.
            CREATE TABLE IF NOT EXISTS homerooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                grade TEXT NOT NULL
            );

            -- A teacher's group for one grade+subject. A student is "in"
            -- a class once linked to that teacher for that subject (see
            -- users.link_student_to_teacher) -- there's no separate
            -- enrollment table, since subject_links already describes
            -- the same relationship.
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                teacher_username TEXT NOT NULL REFERENCES users(username),
                grade TEXT NOT NULL,
                subject TEXT NOT NULL,
                UNIQUE (teacher_username, grade, subject)
            );

            CREATE TABLE IF NOT EXISTS teaching_assignments (
                teacher_username TEXT NOT NULL REFERENCES users(username),
                grade TEXT NOT NULL,
                subject TEXT NOT NULL,
                PRIMARY KEY (teacher_username, grade, subject)
            );

            CREATE TABLE IF NOT EXISTS subject_links (
                student_username TEXT NOT NULL REFERENCES users(username),
                teacher_username TEXT NOT NULL REFERENCES users(username),
                grade TEXT NOT NULL,
                subject TEXT NOT NULL,
                PRIMARY KEY (student_username, teacher_username, grade, subject)
            );

            -- `mode` is only meaningful for Logos chats ("draft" or
            -- "analyze"); NULL for Socrates/Artemis chats. It's what lets
            -- ongoing messages in an "analyze" chat keep using only the
            -- baked-in student activity summary, never mixing in a
            -- teacher's exam-material RAG context meant for drafting.
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL REFERENCES users(username),
                grade TEXT NOT NULL,
                subject TEXT NOT NULL,
                mode TEXT
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                chat_id INTEGER NOT NULL REFERENCES chats(id),
                position INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT,
                PRIMARY KEY (chat_id, position)
            );

            -- A test/exam a teacher saved after drafting it with Logos
            -- (see exams.py). `content` holds the saved freeform draft
            -- text; `published_at` is set once a structured (multiple
            -- choice) version of it has been published for students to
            -- complete -- see test_questions and test_submissions below.
            CREATE TABLE IF NOT EXISTS tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_username TEXT NOT NULL REFERENCES users(username),
                grade TEXT NOT NULL,
                subject TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                published_at TEXT
            );

            -- One multiple-choice question belonging to a published test.
            CREATE TABLE IF NOT EXISTS test_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL REFERENCES tests(id),
                position INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option TEXT NOT NULL
            );

            -- A student's one attempt at a published test (one row per
            -- student per test, enforced by the UNIQUE constraint).
            CREATE TABLE IF NOT EXISTS test_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL REFERENCES tests(id),
                student_username TEXT NOT NULL REFERENCES users(username),
                submitted_at TEXT NOT NULL,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                UNIQUE (test_id, student_username)
            );

            -- One flashcard per question a student got wrong on a test,
            -- created automatically at submission time (see
            -- exams.submit_test). No LLM involved -- the question text
            -- and correct option are already right there.
            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_username TEXT NOT NULL REFERENCES users(username),
                test_id INTEGER NOT NULL REFERENCES tests(id),
                question_text TEXT NOT NULL,
                correct_answer_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            -- A logged-in browser session, identified by a random token
            -- kept in the URL's query string (see sessions.py). Lets a
            -- restart of the Streamlit server (which wipes its in-memory
            -- st.session_state) log the user back in automatically,
            -- since the token survives in the browser's URL and this
            -- table survives in the database.
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                username TEXT NOT NULL REFERENCES users(username),
                created_at TEXT NOT NULL
            );

            -- Individual questions a teacher saves for reuse (see
            -- questions.py). Logos can reference these when starting a
            -- new test-drafting chat for the matching grade+subject.
            -- ON DELETE CASCADE keeps the bank tidy if a teacher account
            -- is ever deleted.
            CREATE TABLE IF NOT EXISTS question_bank (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_username TEXT NOT NULL
                    REFERENCES users(username) ON DELETE CASCADE,
                grade TEXT NOT NULL,
                subject TEXT NOT NULL,
                question_text TEXT NOT NULL,
                answer_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        # Migration: older databases were created before chat_messages had
        # a created_at column.
        existing_chat_message_columns = [
            row["name"] for row in connection.execute("PRAGMA table_info(chat_messages)")
        ]
        if "created_at" not in existing_chat_message_columns:
            connection.execute("ALTER TABLE chat_messages ADD COLUMN created_at TEXT")

        # Migration: older databases had a `tests` table without content,
        # from before Logos could actually draft and save one.
        existing_test_columns = [
            row["name"] for row in connection.execute("PRAGMA table_info(tests)")
        ]
        if existing_test_columns and "content" not in existing_test_columns:
            connection.execute("ALTER TABLE tests ADD COLUMN content TEXT")

        # Migration: older databases had a `tests` table without
        # published_at, from before structured tests could be published.
        if existing_test_columns and "published_at" not in existing_test_columns:
            connection.execute("ALTER TABLE tests ADD COLUMN published_at TEXT")

        # Migration: older databases were created before chats had a mode
        # column (back when Logos only had one chat flavor).
        existing_chat_columns = [
            row["name"] for row in connection.execute("PRAGMA table_info(chats)")
        ]
        if "mode" not in existing_chat_columns:
            connection.execute("ALTER TABLE chats ADD COLUMN mode TEXT")

        # Migration: older databases had users.class_id (the old homeroom
        # link) instead of users.homeroom_id. Copy the values across;
        # class_id itself is left in place, unused, rather than risk an
        # unsupported DROP COLUMN on an older SQLite.
        existing_user_columns = [
            row["name"] for row in connection.execute("PRAGMA table_info(users)")
        ]
        if "homeroom_id" not in existing_user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN homeroom_id INTEGER REFERENCES homerooms(id)"
            )
            if "class_id" in existing_user_columns:
                connection.execute("UPDATE users SET homeroom_id = class_id")

        # Migration: older databases were created before users had an
        # encrypted_password column (see crypto.py). Existing accounts'
        # plaintext passwords were never stored anywhere, so this stays
        # NULL for them until their password is reset.
        if "encrypted_password" not in existing_user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN encrypted_password TEXT")

        connection.commit()
    finally:
        connection.close()
