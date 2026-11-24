"""Keeps the SQLite database alive across restarts on hosts whose disk is
wiped every time (Streamlit Community Cloud), by backing the file up to
Supabase Storage (free plan) and restoring it on startup.

Every query in the app stays plain local SQLite -- only the file itself
is copied:
- restore_on_startup() runs once per server process, BEFORE db.init_db(),
  and downloads the last backup if there's no trusted local copy.
- A background thread uploads a consistent copy (sqlite3's backup API)
  whenever the file has changed, at most every SYNC_INTERVAL_SECONDS, plus
  an hourly snapshot as a safety net (24 rotating slots, so nothing,
  including deleted accounts, survives in backups for more than a day). flush_now() uploads
  immediately (used right after a signup) and also runs at exit.

Safety rule: uploads are only ever enabled after the startup restore
either succeeded or Supabase definitely said "there is no backup yet".
Any other failure (network error, paused project, bad key) leaves
uploads OFF for that process, so a fresh empty database can never be
uploaded over the real backup. A marker file next to the database
records that the local copy is trusted (it came from, or was checked
against, the backup); a local file without it is never uploaded over
an existing backup.

Does nothing at all unless SUPABASE_URL, SUPABASE_SERVICE_KEY and
SUPABASE_BUCKET are all set (see config.py) -- local runs and the full
demo site are unaffected.

Known limit: if the server is killed abruptly, changes from the last
SYNC_INTERVAL_SECONDS can be lost. Streamlit Cloud runs a single server
process, so there's only ever one writer and no merge conflicts.
"""

import atexit
import os
import sqlite3
import tempfile
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from tutorai import config

SYNC_INTERVAL_SECONDS = 15
SNAPSHOT_INTERVAL_SECONDS = 60 * 60
REQUEST_TIMEOUT_SECONDS = 30
LATEST_OBJECT_NAME = "tutorai.db"
SQLITE_HEADER = b"SQLite format 3\x00"

_lock = threading.Lock()
_uploads_enabled = False
_sync_thread_started = False
_last_uploaded_signature = None
_last_snapshot_time = 0.0
_last_error: Optional[str] = None
_last_success_time: Optional[float] = None


def is_configured() -> bool:
    return bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY and config.SUPABASE_BUCKET)


def uploads_enabled() -> bool:
    return _uploads_enabled


def get_last_error() -> Optional[str]:
    """The most recent restore/upload problem, for the admin's main menu
    (None if everything is fine or persistence is off)."""
    return _last_error


def get_last_success_time() -> Optional[float]:
    return _last_success_time


def _marker_path() -> str:
    return config.DB_PATH + ".backup-ok"


def _object_url(object_name: str) -> str:
    return (
        f"{config.SUPABASE_URL}/storage/v1/object/"
        f"{config.SUPABASE_BUCKET}/{object_name}"
    )


def _auth_headers() -> dict:
    """Both Supabase key styles work: the newer "secret" keys (sb_secret_...)
    go only in the apikey header, while the legacy service_role key is a
    JWT that is also sent as the Bearer token."""
    key = config.SUPABASE_SERVICE_KEY
    headers = {"apikey": key}
    if key.startswith("eyJ"):  # a JWT, i.e. the legacy service_role key
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _is_not_found(response) -> bool:
    """Supabase Storage answers a missing object with either a plain 404 or
    a 400 whose JSON body says statusCode "404" / error "not_found",
    depending on version."""
    if response.status_code == 404:
        return True
    if response.status_code == 400:
        try:
            body = response.json()
        except ValueError:
            return False
        return str(body.get("statusCode")) == "404" or str(body.get("error")).lower() in (
            "not_found",
            "not found",
        )
    return False


def _file_signature(path: str) -> tuple:
    stat = os.stat(path)
    return (stat.st_mtime_ns, stat.st_size)


def _mark_local_copy_trusted() -> None:
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
    with open(_marker_path(), "w") as marker:
        marker.write(datetime.now(timezone.utc).isoformat())


def _fail(message: str) -> str:
    global _uploads_enabled, _last_error
    _uploads_enabled = False
    _last_error = message
    if os.path.exists(_marker_path()):
        os.remove(_marker_path())
    return "failed"


def restore_on_startup() -> str:
    """Bring back the database from the backup before anything opens it.

    Returns "disabled" (persistence not configured), "kept_local" (a
    trusted local copy already exists, e.g. the process restarted in the
    same container), "restored", "fresh" (no backup exists yet), or
    "failed" (uploads stay off for this process, see the module docstring).
    """
    global _uploads_enabled, _last_error, _last_uploaded_signature
    if not is_configured():
        return "disabled"

    if os.path.exists(config.DB_PATH) and os.path.exists(_marker_path()):
        _uploads_enabled = True
        _last_error = None
        return "kept_local"

    try:
        response = requests.get(
            _object_url(LATEST_OBJECT_NAME),
            headers=_auth_headers(),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        return _fail(f"Could not reach Supabase to restore the database: {error}")

    if response.ok:
        content = response.content
        if not content.startswith(SQLITE_HEADER):
            return _fail("The backup in Supabase isn't a valid SQLite file.")
        db_dir = os.path.dirname(config.DB_PATH) or "."
        os.makedirs(db_dir, exist_ok=True)
        file_descriptor, temp_path = tempfile.mkstemp(dir=db_dir, suffix=".restore")
        with os.fdopen(file_descriptor, "wb") as temp_file:
            temp_file.write(content)
        os.replace(temp_path, config.DB_PATH)
        _mark_local_copy_trusted()
        _uploads_enabled = True
        _last_error = None
        _last_uploaded_signature = _file_signature(config.DB_PATH)
        return "restored"

    if _is_not_found(response):
        # Nothing backed up yet: whatever is local (usually nothing) is
        # all the data there is, so it's safe to start uploading it.
        _mark_local_copy_trusted()
        _uploads_enabled = True
        _last_error = None
        return "fresh"

    return _fail(
        f"Supabase answered HTTP {response.status_code} when restoring the database "
        "(is the project paused, or a secret wrong?)."
    )


def _consistent_copy_bytes() -> bytes:
    """Copy the live database with sqlite3's backup API, which is safe
    even if another thread is writing at the same moment."""
    db_dir = os.path.dirname(config.DB_PATH) or "."
    file_descriptor, temp_path = tempfile.mkstemp(dir=db_dir, suffix=".upload")
    os.close(file_descriptor)
    try:
        source = sqlite3.connect(config.DB_PATH)
        target = sqlite3.connect(temp_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        with open(temp_path, "rb") as copy_file:
            return copy_file.read()
    finally:
        os.remove(temp_path)


def _upload(object_name: str, content: bytes) -> bool:
    global _last_error
    try:
        response = requests.post(
            _object_url(object_name),
            headers={
                **_auth_headers(),
                "x-upsert": "true",
                "Content-Type": "application/octet-stream",
            },
            data=content,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        _last_error = f"Backup upload failed: {error}"
        return False
    if not response.ok:
        _last_error = f"Backup upload failed: HTTP {response.status_code} {response.text[:200]}"
        return False
    return True


def flush_now() -> bool:
    """Upload the database now if it changed since the last upload.
    Returns True if an upload happened and succeeded."""
    global _last_uploaded_signature, _last_snapshot_time, _last_error, _last_success_time
    if not _uploads_enabled or not os.path.exists(config.DB_PATH):
        return False

    with _lock:
        signature = _file_signature(config.DB_PATH)
        if signature == _last_uploaded_signature:
            return False

        content = _consistent_copy_bytes()
        if not _upload(LATEST_OBJECT_NAME, content):
            return False
        _last_uploaded_signature = signature
        _last_error = None
        _last_success_time = time.time()

        if time.time() - _last_snapshot_time >= SNAPSHOT_INTERVAL_SECONDS:
            # 24 rotating slots (one per hour of the day), each overwritten
            # a day later -- so a deleted account is also gone from every
            # backup within 24 hours, as the privacy notice promises.
            hour_slot = datetime.now(timezone.utc).strftime("%H")
            if _upload(f"snapshots/tutorai-hour-{hour_slot}.db", content):
                _last_snapshot_time = time.time()
        return True


def _sync_loop() -> None:
    global _last_error
    while True:
        time.sleep(SYNC_INTERVAL_SECONDS)
        try:
            flush_now()
        except Exception as error:  # never let the sync thread die
            _last_error = f"Backup failed: {error}"


def start_background_sync() -> None:
    """Start the upload thread (once per process). No-op if uploads are off."""
    global _sync_thread_started
    if not _uploads_enabled or _sync_thread_started:
        return
    threading.Thread(target=_sync_loop, daemon=True, name="tutorai-db-backup").start()
    atexit.register(flush_now)
    _sync_thread_started = True
