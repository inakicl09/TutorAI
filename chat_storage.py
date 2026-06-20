"""Save and load each student's chats, so they're still there after
restarting the app. Each user gets their own file under data/chats.
"""

import json
import os

import config


def _chat_file_path(username: str) -> str:
    return os.path.join(config.CHATS_DIR, f"{username}.json")


def load_chats(username: str) -> list[dict]:
    """Return the student's saved chats, or an empty list if they have
    none yet."""
    file_path = _chat_file_path(username)
    if not os.path.exists(file_path):
        return []

    with open(file_path, "r", encoding="utf-8") as chats_file:
        return json.load(chats_file)


def save_chats(username: str, chats: list[dict]) -> None:
    """Write the student's chats to disk."""
    os.makedirs(config.CHATS_DIR, exist_ok=True)
    with open(_chat_file_path(username), "w", encoding="utf-8") as chats_file:
        json.dump(chats, chats_file, indent=2, ensure_ascii=False)
