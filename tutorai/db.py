"""Single SQLite database for TutorAI: users, chats, and (eventually)
tests. Centralized here so every module talks to the same schema.
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
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                grade TEXT,
                join_code TEXT UNIQUE,
                class_id INTEGER REFERENCES classes(id)
            );

            -- One classroom group per grade (e.g. "1º ESO - A"). Only one
            -- class per grade exists for now, but it's a real table so
            -- more can be added later without changing the data model.
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                grade TEXT NOT NULL
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

        # Migration: older databases were created before users had a
        # class_id column (and before the classes table existed).
        existing_user_columns = [
            row["name"] for row in connection.execute("PRAGMA table_info(users)")
        ]
        if "class_id" not in existing_user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN class_id INTEGER REFERENCES classes(id)")

        connection.commit()
    finally:
        connection.close()
