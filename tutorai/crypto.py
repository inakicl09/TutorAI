"""Reversible encryption for passwords, so the admin can view a user's
actual password (a deliberate security tradeoff the user explicitly
asked for, despite the recommendation to use password resets instead).

This is separate from the PBKDF2 hash in users.py, which is still what
actually verifies logins -- that hash is never reversed. This module
only feeds the admin-facing "view password" feature.

The encryption key lives in a local file (config.SECRET_KEY_PATH),
generated on first use. Treat it like a master password: anyone who
gets it can decrypt every stored password, so it must never be
committed to git (see .gitignore) or shared.
"""

import os

from cryptography.fernet import Fernet

from tutorai import config


def _load_or_create_key() -> bytes:
    if os.path.exists(config.SECRET_KEY_PATH):
        with open(config.SECRET_KEY_PATH, "rb") as key_file:
            return key_file.read()

    key = Fernet.generate_key()
    os.makedirs(os.path.dirname(config.SECRET_KEY_PATH), exist_ok=True)
    with open(config.SECRET_KEY_PATH, "wb") as key_file:
        key_file.write(key)
    return key


def encrypt_password(password: str) -> str:
    fernet = Fernet(_load_or_create_key())
    return fernet.encrypt(password.encode("utf-8")).decode("utf-8")


def decrypt_password(encrypted_password: str) -> str:
    fernet = Fernet(_load_or_create_key())
    return fernet.decrypt(encrypted_password.encode("utf-8")).decode("utf-8")
