"""persistence.py talks to Supabase Storage over HTTP, so these tests mock
`requests` instead of needing a real bucket."""

import os
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
import requests

from tutorai import config, persistence, users


@pytest.fixture(autouse=True)
def reset_persistence_state(monkeypatch):
    monkeypatch.setattr(persistence, "_uploads_enabled", False)
    monkeypatch.setattr(persistence, "_last_uploaded_signature", None)
    monkeypatch.setattr(persistence, "_last_snapshot_time", 0.0)
    monkeypatch.setattr(persistence, "_last_error", None)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_KEY", "service-key")
    monkeypatch.setattr(config, "SUPABASE_BUCKET", "tutorai-backups")


def _response(status_code: int, content: bytes = b"", json_body=None):
    response = MagicMock()
    response.status_code = status_code
    response.ok = 200 <= status_code < 300
    response.content = content
    response.text = ""
    if json_body is None:
        response.json.side_effect = ValueError("no json")
    else:
        response.json.return_value = json_body
    return response


def test_does_nothing_without_secrets():
    with patch("tutorai.persistence.requests") as mock_requests:
        assert persistence.restore_on_startup() == "disabled"
        assert persistence.flush_now() is False
    mock_requests.get.assert_not_called()
    mock_requests.post.assert_not_called()


@pytest.mark.parametrize(
    "not_found",
    [
        _response(404),
        _response(400, json_body={"statusCode": "404", "error": "not_found"}),
    ],
)
def test_no_backup_yet_starts_fresh_and_enables_uploads(configured, tmp_path, not_found):
    os.remove(config.DB_PATH)
    with patch("tutorai.persistence.requests.get", return_value=not_found):
        assert persistence.restore_on_startup() == "fresh"
    assert persistence.uploads_enabled()


def test_network_error_disables_uploads(configured):
    users.create_student("ana", "pw", "1º ESO")
    with patch(
        "tutorai.persistence.requests.get",
        side_effect=requests.ConnectionError("offline"),
    ):
        assert persistence.restore_on_startup() == "failed"

    assert not persistence.uploads_enabled()
    assert persistence.get_last_error()
    with patch("tutorai.persistence.requests.post") as mock_post:
        assert persistence.flush_now() is False
    mock_post.assert_not_called()


def test_server_error_disables_uploads(configured):
    with patch("tutorai.persistence.requests.get", return_value=_response(500)):
        assert persistence.restore_on_startup() == "failed"
    assert not persistence.uploads_enabled()


def test_restore_writes_the_backup_over_a_missing_local_file(configured, tmp_path):
    # Build a "remote" database holding one student, then lose the local one.
    users.create_student("ana", "pw", "1º ESO")
    with open(config.DB_PATH, "rb") as db_file:
        backup_bytes = db_file.read()
    os.remove(config.DB_PATH)

    with patch(
        "tutorai.persistence.requests.get", return_value=_response(200, backup_bytes)
    ):
        assert persistence.restore_on_startup() == "restored"

    assert users.verify_login("ana", "pw")
    assert persistence.uploads_enabled()


def test_restore_rejects_a_file_that_is_not_sqlite(configured):
    with patch(
        "tutorai.persistence.requests.get", return_value=_response(200, b"<html>oops</html>")
    ):
        assert persistence.restore_on_startup() == "failed"
    assert not persistence.uploads_enabled()


def test_trusted_local_copy_is_kept_without_downloading(configured):
    with patch("tutorai.persistence.requests.get", return_value=_response(404)):
        persistence.restore_on_startup()

    with patch("tutorai.persistence.requests.get") as mock_get:
        assert persistence.restore_on_startup() == "kept_local"
    mock_get.assert_not_called()


def test_flush_uploads_a_valid_sqlite_copy_once_per_change(configured, tmp_path):
    with patch("tutorai.persistence.requests.get", return_value=_response(404)):
        persistence.restore_on_startup()

    users.create_student("ana", "pw", "1º ESO")
    with patch(
        "tutorai.persistence.requests.post", return_value=_response(200)
    ) as mock_post:
        assert persistence.flush_now() is True
        # Unchanged file: nothing to upload.
        assert persistence.flush_now() is False

    # First flush uploads the latest copy plus an hourly snapshot.
    uploaded_urls = [c.args[0] for c in mock_post.call_args_list]
    assert uploaded_urls[0].endswith("/storage/v1/object/tutorai-backups/tutorai.db")
    assert "/snapshots/tutorai-" in uploaded_urls[1]
    assert mock_post.call_args_list[0].kwargs["headers"]["x-upsert"] == "true"

    uploaded_copy = tmp_path / "uploaded.db"
    uploaded_copy.write_bytes(mock_post.call_args_list[0].kwargs["data"])
    connection = sqlite3.connect(uploaded_copy)
    try:
        assert connection.execute(
            "SELECT username FROM users WHERE username = 'ana'"
        ).fetchone() == ("ana",)
    finally:
        connection.close()


def test_failed_upload_is_reported_and_retried(configured):
    with patch("tutorai.persistence.requests.get", return_value=_response(404)):
        persistence.restore_on_startup()
    users.create_student("ana", "pw", "1º ESO")

    with patch("tutorai.persistence.requests.post", return_value=_response(503)):
        assert persistence.flush_now() is False
    assert persistence.get_last_error()

    with patch("tutorai.persistence.requests.post", return_value=_response(200)):
        assert persistence.flush_now() is True
    assert persistence.get_last_error() is None


@pytest.mark.parametrize(
    "key, expects_bearer",
    [("sb_secret_abc123", False), ("eyJhbGciOiJIUzI1NiJ9.payload.sig", True)],
)
def test_auth_headers_support_both_supabase_key_styles(monkeypatch, key, expects_bearer):
    monkeypatch.setattr(config, "SUPABASE_SERVICE_KEY", key)
    headers = persistence._auth_headers()
    assert headers["apikey"] == key
    assert ("Authorization" in headers) == expects_bearer
