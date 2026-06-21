"""Shared pytest fixtures: every test gets its own throwaway SQLite
database and password-encryption key, instead of touching
data/tutorai.db or data/secret.key.
"""

import pytest

from tutorai import config, db


@pytest.fixture(autouse=True)
def temp_database(tmp_path, monkeypatch):
    db_path = tmp_path / "test_tutorai.db"
    monkeypatch.setattr(config, "DB_PATH", str(db_path))
    monkeypatch.setattr(config, "SECRET_KEY_PATH", str(tmp_path / "test_secret.key"))
    db.init_db()
