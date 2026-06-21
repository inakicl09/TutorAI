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

            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL REFERENCES users(username),
                grade TEXT NOT NULL,
                subject TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                chat_id INTEGER NOT NULL REFERENCES chats(id),
                position INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT,
                PRIMARY KEY (chat_id, position)
            );

            -- Not used yet: teachers' "create tests" feature is still a
            -- stub, but the table is ready for when that's built.
            CREATE TABLE IF NOT EXISTS tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_username TEXT NOT NULL REFERENCES users(username),
                grade TEXT NOT NULL,
                subject TEXT NOT NULL,
                title TEXT NOT NULL
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

        connection.commit()
    finally:
        connection.close()
