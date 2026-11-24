"""project_end.py deletes every tester's data on the test site's end
date. Supabase is mocked with `requests`; nothing touches a real bucket."""

import os
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from tutorai import config, persistence, project_end, users


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_KEY", "sb_secret_x")
    monkeypatch.setattr(config, "SUPABASE_BUCKET", "tutorai-backups")
    monkeypatch.setattr(persistence, "_uploads_enabled", False)
    monkeypatch.setattr(persistence, "_permanently_disabled", False)
    monkeypatch.setattr(persistence, "_last_uploaded_signature", None)


def _ok(json_body=None):
    response = MagicMock()
    response.ok = True
    response.status_code = 200
    response.json.return_value = json_body
    response.raise_for_status.return_value = None
    return response


def _listing(prefix_to_entries):
    def fake_post(url, headers, json, timeout):
        return _ok(prefix_to_entries.get(json["prefix"], []))
    return fake_post


def test_project_is_over_from_the_end_date_itself(monkeypatch):
    monkeypatch.setattr(config, "PROJECT_END_DATE", "2027-06-30")
    assert not project_end.is_project_over(date(2027, 6, 29))
    assert project_end.is_project_over(date(2027, 6, 30))
    assert project_end.is_project_over(date(2028, 1, 1))


def test_default_end_date_is_30_june_2027():
    assert project_end.end_date() == date(2027, 6, 30)


def test_delete_all_backups_deletes_every_file_but_not_folder_entries(configured):
    listing = {
        "": [{"name": "snapshots", "id": None}, {"name": "tutorai.db", "id": "1"}],
        "snapshots": [{"name": "tutorai-hour-03.db", "id": "2"}, {"name": "tutorai-20261124-20.db", "id": "3"}],
    }
    with patch("tutorai.project_end.requests.post", side_effect=_listing(listing)), patch(
        "tutorai.project_end.requests.delete", return_value=_ok()
    ) as mock_delete:
        deleted = project_end.delete_all_backups()

    expected = ["tutorai.db", "snapshots/tutorai-hour-03.db", "snapshots/tutorai-20261124-20.db"]
    assert deleted == expected
    assert mock_delete.call_args.kwargs["json"] == {"prefixes": expected}


def test_dry_run_deletes_nothing(configured):
    with patch(
        "tutorai.project_end.requests.post",
        side_effect=_listing({"": [{"name": "tutorai.db", "id": "1"}]}),
    ), patch("tutorai.project_end.requests.delete") as mock_delete:
        assert project_end.delete_all_backups(dry_run=True) == ["tutorai.db"]
    mock_delete.assert_not_called()


def test_wipe_everything_removes_local_data_and_stops_backups(configured, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setattr(config, "DOCUMENTS_DIR", str(tmp_path / "documents"))
    os.makedirs(config.CHROMA_DIR)
    os.makedirs(config.DOCUMENTS_DIR)
    users.create_student("ana", "pw", "1º ESO")
    with patch("tutorai.persistence.requests.get", return_value=MagicMock(status_code=404, ok=False)):
        persistence.restore_on_startup()
    assert persistence.uploads_enabled()

    with patch("tutorai.project_end.requests.post", side_effect=_listing({})), patch(
        "tutorai.project_end.requests.delete"
    ):
        assert project_end.wipe_everything() is None

    assert not os.path.exists(config.DB_PATH)
    assert not os.path.exists(config.CHROMA_DIR)
    assert not os.path.exists(config.DOCUMENTS_DIR)
    assert not persistence.uploads_enabled()
    # Even if something recreates the database, it's never uploaded again,
    # and a restore is refused.
    with patch("tutorai.persistence.requests.post") as mock_upload:
        assert persistence.flush_now() is False
    mock_upload.assert_not_called()
    assert persistence.restore_on_startup() == "disabled"


def test_wipe_everything_reports_a_failed_backup_deletion(configured):
    import requests

    with patch(
        "tutorai.project_end.requests.post", side_effect=requests.ConnectionError("offline")
    ):
        assert "Could not delete" in project_end.wipe_everything()


def test_cli_before_the_end_date_deletes_nothing(configured, monkeypatch, capsys):
    monkeypatch.setattr(config, "PROJECT_END_DATE", "2999-01-01")
    monkeypatch.setattr("sys.argv", ["project_end"])
    with patch("tutorai.project_end.requests") as mock_requests:
        project_end.main()
    mock_requests.delete.assert_not_called()
    assert "nothing deleted" in capsys.readouterr().out


def test_cli_on_the_end_date_deletes_backups(configured, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_END_DATE", "2000-01-01")
    monkeypatch.setattr("sys.argv", ["project_end"])
    with patch(
        "tutorai.project_end.requests.post",
        side_effect=_listing({"": [{"name": "tutorai.db", "id": "1"}]}),
    ), patch("tutorai.project_end.requests.delete", return_value=_ok()) as mock_delete:
        project_end.main()
    mock_delete.assert_called_once()
