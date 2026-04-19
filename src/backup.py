"""Database backup with rotating daily+weekly snapshot retention.

Uses SQLite's online backup API so backups are safe even if the source
database is open. Snapshots are gzip-compressed and written atomically
via a temp file rename. Retention policy: keep the newest backup for each
of the last 7 distinct calendar days, plus the newest backup for each of
the next 4 distinct ISO weeks beyond the daily window. Older backups are
deleted on every run.
"""
import gzip
import os
import re
import shutil
import sqlite3
from datetime import datetime

from database import DATABASE_PATH

BACKUP_DIR_DEFAULT = os.path.join(os.path.expanduser("~"), "nhl_backups")
BACKUP_FILENAME_PREFIX = "nhl_data"
BACKUP_FILENAME_SUFFIX = ".db.gz"
BACKUP_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%S"
_BACKUP_FILENAME_PATTERN = re.compile(
    r"^" + re.escape(BACKUP_FILENAME_PREFIX) + r"_(\d{8}T\d{6})"
    + re.escape(BACKUP_FILENAME_SUFFIX) + r"$"
)

DAILY_BACKUPS_TO_KEEP = 7
WEEKLY_BACKUPS_TO_KEEP = 4

_TMP_DB_SUFFIX = ".tmp.db"
_TMP_GZ_SUFFIX = ".tmp"


def backup_database(source_path=DATABASE_PATH, backup_dir=BACKUP_DIR_DEFAULT,
                    now=None):
    """Create a gzip-compressed snapshot of source_path in backup_dir.

    Uses SQLite's online backup API into a temp file, gzips the result, then
    renames into the final path so partial backups never remain on disk.
    Returns the absolute path of the written backup.
    """
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"Source database not found: {source_path}")

    os.makedirs(backup_dir, exist_ok=True)
    now = now or datetime.now()
    timestamp = now.strftime(BACKUP_TIMESTAMP_FORMAT)
    final_name = (f"{BACKUP_FILENAME_PREFIX}_{timestamp}"
                  f"{BACKUP_FILENAME_SUFFIX}")
    final_path = os.path.join(backup_dir, final_name)
    tmp_db_path = final_path + _TMP_DB_SUFFIX
    tmp_gz_path = final_path + _TMP_GZ_SUFFIX

    try:
        src_conn = sqlite3.connect(source_path)
        dst_conn = sqlite3.connect(tmp_db_path)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        with open(tmp_db_path, "rb") as f_in:
            with gzip.open(tmp_gz_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        os.replace(tmp_gz_path, final_path)
    finally:
        for leftover in (tmp_db_path, tmp_gz_path):
            if os.path.exists(leftover):
                try:
                    os.remove(leftover)
                except OSError:
                    pass

    return final_path


def _parse_backup_timestamp(filename):
    """Return datetime from a backup filename, or None if it doesn't match."""
    match = _BACKUP_FILENAME_PATTERN.match(filename)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), BACKUP_TIMESTAMP_FORMAT)
    except ValueError:
        return None


def _list_backups(backup_dir):
    """Return (datetime, path) pairs for valid backups in backup_dir, newest first."""
    if not os.path.isdir(backup_dir):
        return []
    entries = []
    for name in os.listdir(backup_dir):
        ts = _parse_backup_timestamp(name)
        if ts is None:
            continue
        entries.append((ts, os.path.join(backup_dir, name)))
    entries.sort(key=lambda e: e[0], reverse=True)
    return entries


def prune_old_backups(backup_dir=BACKUP_DIR_DEFAULT,
                      daily_to_keep=DAILY_BACKUPS_TO_KEEP,
                      weekly_to_keep=WEEKLY_BACKUPS_TO_KEEP):
    """Delete backups outside the daily+weekly retention window.

    Keeps the newest backup for each of the `daily_to_keep` most recent
    distinct calendar days, plus the newest backup for each of the
    `weekly_to_keep` most recent distinct ISO weeks that are not already
    covered by the daily retention. Returns the list of deleted paths.
    """
    backups = _list_backups(backup_dir)
    if not backups:
        return []

    kept = set()
    seen_days = set()
    weeks_from_dailies = set()
    for ts, path in backups:
        day_key = ts.date()
        if day_key in seen_days:
            continue
        if len(seen_days) >= daily_to_keep:
            break
        seen_days.add(day_key)
        iso_year, iso_week, _ = ts.isocalendar()
        weeks_from_dailies.add((iso_year, iso_week))
        kept.add(path)

    seen_weeks = set()
    for ts, path in backups:
        if path in kept:
            continue
        iso_year, iso_week, _ = ts.isocalendar()
        week_key = (iso_year, iso_week)
        if week_key in weeks_from_dailies:
            continue
        if week_key in seen_weeks:
            continue
        if len(seen_weeks) >= weekly_to_keep:
            break
        seen_weeks.add(week_key)
        kept.add(path)

    deleted = []
    for _, path in backups:
        if path in kept:
            continue
        try:
            os.remove(path)
            deleted.append(path)
        except OSError:
            pass
    return deleted


def run_backup_cycle(source_path=DATABASE_PATH, backup_dir=BACKUP_DIR_DEFAULT):
    """Create a fresh backup and prune old ones. Returns (new_path, deleted)."""
    new_path = backup_database(source_path, backup_dir)
    deleted = prune_old_backups(backup_dir)
    return new_path, deleted


def run_backup_cycle_safe(source_path=DATABASE_PATH,
                          backup_dir=BACKUP_DIR_DEFAULT):
    """Best-effort wrapper around run_backup_cycle.

    A backup failure at end-of-scrape must not crash the pipeline, since
    the scraped data is more valuable than the backup attempt. Logs and
    swallows any exception, returning the new path on success or None on
    failure.
    """
    try:
        new_path, deleted = run_backup_cycle(source_path, backup_dir)
        print(f"Backup created: {new_path}")
        if deleted:
            print(f"Pruned {len(deleted)} old backup(s)")
        return new_path
    except Exception as exc:
        print(f"WARNING: backup failed: {exc}")
        return None
