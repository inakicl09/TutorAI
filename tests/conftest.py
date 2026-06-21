"""Shared pytest fixtures: every test gets its own throwaway SQLite
database instead of touching data/tutorai.db.
"""

import pytest

from tutorai import classes, config, db


@pytest.fixture(autouse=True)
def temp_database(tmp_path, monkeypatch):
    db_path = tmp_path / "test_tutorai.db"
    monkeypatch.setattr(config, "DB_PATH", str(db_path))
    db.init_db()
    classes.ensure_default_classes()
