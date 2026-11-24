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
    # project_end.wipe_local_data deletes these folders; tests must never
    # point it at the real data/ directory (it once did, see CLAUDE.md).
    monkeypatch.setattr(config, "CHROMA_DIR", str(tmp_path / "chroma_db"))
    monkeypatch.setattr(config, "DOCUMENTS_DIR", str(tmp_path / "documents"))
    # Keep tests independent of whatever secrets the shell happens to have.
    monkeypatch.setattr(config, "SECRET_KEY", "")
    monkeypatch.setattr(config, "SUPABASE_URL", "")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_KEY", "")
    monkeypatch.setattr(config, "SUPABASE_BUCKET", "")
    monkeypatch.setattr(config, "PUBLIC_TEST_MODE", False)
    monkeypatch.setattr(config, "PROJECT_END_DATE", "2027-06-30")
    db.init_db()
