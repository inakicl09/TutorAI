"""Automatic end of the public test site: on config.PROJECT_END_DATE
(30 June 2027) every tester's data is deleted, as the privacy notice
promises. The user asked for this to happen by itself, so nobody has to
remember to do it.

Two independent paths do the deleting, because each one covers a case
the other can't:
- app.py calls close_site_if_over() at the very top of every page load on
  the test site. From the end date on, it wipes the local database,
  uploaded documents and key file, deletes every backup in Supabase,
  turns backups off for good, and shows only a "the project has ended"
  page -- nothing can be restored, logged into or stored again.
- A daily GitHub Actions workflow (.github/workflows/delete-test-data.yml)
  runs `python -m tutorai.project_end`, which deletes the Supabase
  backups on/after the end date even if nobody ever opens the site again
  (a sleeping Streamlit app runs no code).

Both are idempotent: running them again after everything is gone just
finds nothing to delete.
"""

import argparse
import os
import shutil
from datetime import date, datetime, timezone
from typing import Optional

import requests

from tutorai import config, persistence

REQUEST_TIMEOUT_SECONDS = 30


def end_date() -> date:
    return date.fromisoformat(config.PROJECT_END_DATE)


def is_project_over(today: Optional[date] = None) -> bool:
    """True from the end date itself onwards (UTC calendar day)."""
    today = today or datetime.now(timezone.utc).date()
    return today >= end_date()


def _list_backup_objects() -> list[str]:
    """Every object path in the backup bucket (top level + snapshots/)."""
    url = f"{config.SUPABASE_URL}/storage/v1/object/list/{config.SUPABASE_BUCKET}"
    headers = {**persistence._auth_headers(), "Content-Type": "application/json"}
    paths = []
    for prefix in ("", "snapshots"):
        response = requests.post(
            url,
            headers=headers,
            json={"prefix": prefix, "limit": 1000, "offset": 0},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        for entry in response.json():
            # Folders come back as entries with no id; their files are
            # listed under their own prefix.
            if entry.get("id") is None:
                continue
            paths.append(f"{prefix}/{entry['name']}" if prefix else entry["name"])
    return paths


def delete_all_backups(dry_run: bool = False) -> list[str]:
    """Delete every object in the Supabase backup bucket and return the
    paths found. Raises on any HTTP failure, so callers can retry later.
    A no-op returning [] when Supabase isn't configured."""
    if not persistence.is_configured():
        return []
    paths = _list_backup_objects()
    if paths and not dry_run:
        response = requests.delete(
            f"{config.SUPABASE_URL}/storage/v1/object/{config.SUPABASE_BUCKET}",
            headers={**persistence._auth_headers(), "Content-Type": "application/json"},
            json={"prefixes": paths},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    return paths


def wipe_local_data() -> None:
    """Delete the local database (and its backup marker), every uploaded
    document and vector store, and the password-encryption key file."""
    for path in (
        config.DB_PATH,
        config.DB_PATH + ".backup-ok",
        config.DB_PATH + "-journal",
        config.SECRET_KEY_PATH,
    ):
        if os.path.exists(path):
            os.remove(path)
    for directory in (config.CHROMA_DIR, config.DOCUMENTS_DIR):
        if os.path.isdir(directory):
            shutil.rmtree(directory)


def wipe_everything() -> Optional[str]:
    """Stop backups for good, then delete all local and backed-up data.
    Returns an error message if deleting the Supabase backups failed
    (it's retried on the next page load and by the daily workflow), or
    None if everything is gone."""
    persistence.disable_permanently()
    wipe_local_data()
    try:
        delete_all_backups()
    except requests.RequestException as error:
        return f"Could not delete the Supabase backups yet: {error}"
    return None


def main() -> None:
    """Entry point for the daily GitHub Actions workflow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="only list what would be deleted (works before the end date too)",
    )
    args = parser.parse_args()

    if not persistence.is_configured():
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_KEY / SUPABASE_BUCKET are not set.")

    print(f"End date: {end_date().isoformat()} | project over: {is_project_over()}")
    if args.dry_run:
        found = delete_all_backups(dry_run=True)
        print(f"Dry run: {len(found)} backup object(s) would be deleted on the end date.")
        return
    if not is_project_over():
        print("Not the end date yet: nothing deleted.")
        return
    deleted = delete_all_backups()
    print(f"Deleted {len(deleted)} backup object(s).")


if __name__ == "__main__":
    main()
