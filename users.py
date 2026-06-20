"""User accounts: signup and login, stored in data/users.json.

Passwords are never stored in plain text. Each one is hashed with a random
salt using hashlib's PBKDF2 implementation (standard library), so even if
the JSON file is read, the original passwords aren't exposed.
"""

import hashlib
import json
import os
import secrets

import config

PBKDF2_ITERATIONS = 200_000


def _load_users() -> dict:
    if not os.path.exists(config.USERS_FILE):
        return {}

    with open(config.USERS_FILE, "r", encoding="utf-8") as users_file:
        return json.load(users_file)


def _save_users(users: dict) -> None:
    os.makedirs(os.path.dirname(config.USERS_FILE), exist_ok=True)
    with open(config.USERS_FILE, "w", encoding="utf-8") as users_file:
        json.dump(users, users_file, indent=2, ensure_ascii=False)


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    ).hex()


def username_exists(username: str) -> bool:
    return username in _load_users()


def create_user(username: str, password: str) -> None:
    """Add a new user account.

    Raises ValueError if the username is already taken.
    """
    users = _load_users()
    if username in users:
        raise ValueError("Username already exists")

    salt = secrets.token_hex(16)
    users[username] = {
        "salt": salt,
        "password_hash": _hash_password(password, salt),
    }
    _save_users(users)


def verify_login(username: str, password: str) -> bool:
    """Check a username/password pair against the stored accounts."""
    users = _load_users()
    user = users.get(username)
    if user is None:
        return False

    return _hash_password(password, user["salt"]) == user["password_hash"]
