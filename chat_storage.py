"""Chat persistence in the shared SQLite database (see db.py): one row
per chat, one row per message, so chats survive restarting the app.
"""

import db


def create_chat(username: str, grade: str, subject: str, system_prompt: str) -> dict:
    """Start a new chat for this student and return it, system message
    included."""
    connection = db.get_connection()
    try:
        cursor = connection.execute(
            "INSERT INTO chats (username, grade, subject) VALUES (?, ?, ?)",
            (username, grade, subject),
        )
        chat_id = cursor.lastrowid
        connection.execute(
            "INSERT INTO chat_messages (chat_id, position, role, content) "
            "VALUES (?, 0, 'system', ?)",
            (chat_id, system_prompt),
        )
        connection.commit()
        return {
            "id": chat_id,
            "grade": grade,
            "subject": subject,
            "history": [{"role": "system", "content": system_prompt}],
        }
    finally:
        connection.close()


def add_message(chat_id: int, role: str, content: str) -> None:
    """Append one message to an existing chat."""
    connection = db.get_connection()
    try:
        next_position = connection.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM chat_messages WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO chat_messages (chat_id, position, role, content) "
            "VALUES (?, ?, ?, ?)",
            (chat_id, next_position, role, content),
        )
        connection.commit()
    finally:
        connection.close()


def load_chats(username: str) -> list[dict]:
    """Return all of a student's chats, oldest first, each with its full
    message history."""
    connection = db.get_connection()
    try:
        chat_rows = connection.execute(
            "SELECT id, grade, subject FROM chats WHERE username = ? ORDER BY id",
            (username,),
        ).fetchall()

        chats = []
        for chat_row in chat_rows:
            message_rows = connection.execute(
                "SELECT role, content FROM chat_messages "
                "WHERE chat_id = ? ORDER BY position",
                (chat_row["id"],),
            ).fetchall()
            chats.append(
                {
                    "id": chat_row["id"],
                    "grade": chat_row["grade"],
                    "subject": chat_row["subject"],
                    "history": [dict(row) for row in message_rows],
                }
            )
        return chats
    finally:
        connection.close()
