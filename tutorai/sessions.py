"""Persistent login sessions, so restarting the Streamlit server doesn't
log everyone out. A random token is kept in the browser's URL query
string (see app.py) and mapped to a username here, in the database --
the in-memory st.session_state is what actually gets wiped on restart,
not the browser's URL or the database.
"""

import secrets
from datetime import datetime, timezone
from typing import Optional

from tutorai import db

TOKEN_BYTES = 32


def create_session(username: str) -> str:
    """Start a new persistent session for this user and return its
    token."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    connection = db.get_connection()
    try:
        connection.execute(
            "INSERT INTO sessions (token, username, created_at) VALUES (?, ?, ?)",
            (token, username, datetime.now(timezone.utc).isoformat()),
        )
        connection.commit()
    finally:
        connection.close()
    return token


def get_username_for_token(token: str) -> Optional[str]:
    """Return the username for a session token, or None if it's unknown
    (e.g. already logged out, or never existed)."""
    connection = db.get_connection()
    try:
        row = connection.execute(
            "SELECT username FROM sessions WHERE token = ?", (token,)
        ).fetchone()
        return row["username"] if row else None
    finally:
        connection.close()


def delete_session(token: str) -> None:
    """End a session (used on logout)."""
    connection = db.get_connection()
    try:
        connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
        connection.commit()
    finally:
        connection.close()


def delete_sessions_for_user(username: str) -> None:
    """End every session belonging to a user (used when their account is
    deleted)."""
    connection = db.get_connection()
    try:
        connection.execute("DELETE FROM sessions WHERE username = ?", (username,))
        connection.commit()
    finally:
        connection.close()
