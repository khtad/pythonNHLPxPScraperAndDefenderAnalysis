import gzip
import os
import sqlite3
from datetime import datetime, timedelta

import pytest

from backup import (
    BACKUP_FILENAME_PREFIX,
    BACKUP_FILENAME_SUFFIX,
    BACKUP_TIMESTAMP_FORMAT,
    DAILY_BACKUPS_TO_KEEP,
    WEEKLY_BACKUPS_TO_KEEP,
    _list_backups,
    _parse_backup_timestamp,
    backup_database,
    prune_old_backups,
    run_backup_cycle,
    run_backup_cycle_safe,
)


@pytest.fixture
def source_db(tmp_path):
    db_path = tmp_path / "source.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE t (k INTEGER PRIMARY KEY, v TEXT)")
        conn.execute("INSERT INTO t (v) VALUES ('hello')")
        conn.execute("INSERT INTO t (v) VALUES ('world')")
        conn.commit()
    finally:
        conn.close()
    return str(db_path)


def _make_dummy_backup(backup_dir, ts):
    name = (f"{BACKUP_FILENAME_PREFIX}_"
            f"{ts.strftime(BACKUP_TIMESTAMP_FORMAT)}"
            f"{BACKUP_FILENAME_SUFFIX}")
    path = os.path.join(backup_dir, name)
    with gzip.open(path, "wb") as f:
        f.write(b"stub")
    return path


def _list_backup_paths(backup_dir):
    return {p for _, p in _list_backups(backup_dir)}


def test_backup_creates_gzipped_file(source_db, tmp_path):
    backup_dir = tmp_path / "backups"
    result = backup_database(source_db, str(backup_dir))
    assert os.path.isfile(result)
    assert result.endswith(BACKUP_FILENAME_SUFFIX)
    assert os.path.dirname(result) == str(backup_dir)


def test_backup_is_valid_sqlite(source_db, tmp_path):
    backup_dir = tmp_path / "backups"
    result = backup_database(source_db, str(backup_dir))

    restored = tmp_path / "restored.db"
    with gzip.open(result, "rb") as f_in, open(restored, "wb") as f_out:
        f_out.write(f_in.read())

    conn = sqlite3.connect(str(restored))
    try:
        rows = sorted(r[0] for r in conn.execute("SELECT v FROM t"))
    finally:
        conn.close()
    assert rows == ["hello", "world"]


def test_backup_creates_missing_dir(source_db, tmp_path):
    backup_dir = tmp_path / "nested" / "backups"
    result = backup_database(source_db, str(backup_dir))
    assert os.path.isdir(str(backup_dir))
    assert os.path.isfile(result)


def test_backup_cleans_up_temp_files_on_success(source_db, tmp_path):
    backup_dir = tmp_path / "backups"
    backup_database(source_db, str(backup_dir))
    stray = [n for n in os.listdir(str(backup_dir)) if ".tmp" in n]
    assert stray == []


def test_backup_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        backup_database(str(tmp_path / "missing.db"),
                        str(tmp_path / "backups"))


def test_backup_fixed_timestamp(source_db, tmp_path):
    backup_dir = tmp_path / "backups"
    fixed = datetime(2026, 4, 19, 15, 30, 0)
    result = backup_database(source_db, str(backup_dir), now=fixed)
    assert os.path.basename(result) == (
        f"{BACKUP_FILENAME_PREFIX}_20260419T153000"
        f"{BACKUP_FILENAME_SUFFIX}"
    )


def test_parse_timestamp_accepts_valid_name():
    ts = _parse_backup_timestamp(
        f"{BACKUP_FILENAME_PREFIX}_20260419T120000{BACKUP_FILENAME_SUFFIX}"
    )
    assert ts == datetime(2026, 4, 19, 12, 0, 0)


def test_parse_timestamp_rejects_invalid_names():
    assert _parse_backup_timestamp("random.txt") is None
    assert _parse_backup_timestamp(
        f"{BACKUP_FILENAME_PREFIX}_bad{BACKUP_FILENAME_SUFFIX}"
    ) is None
    assert _parse_backup_timestamp(
        f"{BACKUP_FILENAME_PREFIX}_20260419T120000.db"
    ) is None


def test_prune_empty_dir_returns_empty(tmp_path):
    assert prune_old_backups(str(tmp_path / "nonexistent")) == []
    empty = tmp_path / "empty"
    empty.mkdir()
    assert prune_old_backups(str(empty)) == []


def test_prune_ignores_unrelated_files(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    unrelated = backup_dir / "readme.txt"
    unrelated.write_text("not a backup")
    _make_dummy_backup(str(backup_dir), datetime(2026, 4, 19))

    prune_old_backups(str(backup_dir))
    assert unrelated.exists()


def test_prune_keeps_7_dailies_and_4_weeklies(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    now = datetime(2026, 4, 19, 12, 0, 0)
    created = [
        _make_dummy_backup(str(backup_dir), now - timedelta(days=d))
        for d in range(60)
    ]

    deleted = prune_old_backups(str(backup_dir))
    remaining = _list_backup_paths(str(backup_dir))

    assert len(remaining) == DAILY_BACKUPS_TO_KEEP + WEEKLY_BACKUPS_TO_KEEP
    assert remaining | set(deleted) == set(created)


def test_prune_keeps_newest_of_multiple_same_day(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    base = datetime(2026, 4, 19, 8, 0, 0)
    early = _make_dummy_backup(str(backup_dir), base)
    mid = _make_dummy_backup(str(backup_dir), base + timedelta(hours=4))
    newest = _make_dummy_backup(str(backup_dir), base + timedelta(hours=8))
    for d in range(1, DAILY_BACKUPS_TO_KEEP):
        _make_dummy_backup(str(backup_dir), base - timedelta(days=d))

    prune_old_backups(str(backup_dir))
    remaining = _list_backup_paths(str(backup_dir))

    assert newest in remaining
    assert early not in remaining
    assert mid not in remaining


def test_prune_weekly_skips_weeks_already_covered_by_dailies(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    now = datetime(2026, 4, 19, 12, 0, 0)
    for d in range(14):
        _make_dummy_backup(str(backup_dir), now - timedelta(days=d))

    prune_old_backups(str(backup_dir),
                      daily_to_keep=7, weekly_to_keep=4)
    remaining = _list_backup_paths(str(backup_dir))

    assert len(remaining) == 7 + 1


def test_run_backup_cycle_creates_new_and_prunes(source_db, tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    old_cutoff = datetime.now() - timedelta(days=365)
    for d in range(40):
        _make_dummy_backup(str(backup_dir), old_cutoff - timedelta(days=d))

    new_path, deleted = run_backup_cycle(source_db, str(backup_dir))

    assert os.path.isfile(new_path)
    assert len(deleted) > 0


def test_run_backup_cycle_safe_returns_none_on_failure(tmp_path, capsys):
    result = run_backup_cycle_safe(
        source_path=str(tmp_path / "nope.db"),
        backup_dir=str(tmp_path / "backups"),
    )
    assert result is None
    captured = capsys.readouterr()
    assert "backup failed" in captured.out.lower()


def test_run_backup_cycle_safe_returns_path_on_success(source_db, tmp_path):
    backup_dir = tmp_path / "backups"
    result = run_backup_cycle_safe(source_path=source_db,
                                   backup_dir=str(backup_dir))
    assert result is not None
    assert os.path.isfile(result)
