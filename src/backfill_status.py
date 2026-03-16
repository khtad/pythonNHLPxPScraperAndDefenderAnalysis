import argparse
import os
import sqlite3

from database import DATABASE_PATH, get_collected_game_ids, get_last_collected_date

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_LOG_FILENAME = "backfill_full.log"
_DEFAULT_TAIL_LINES = 10
_READ_ENCODINGS = ("utf-16", "utf-8", "utf-8-sig")

_TABLE_GAMES = "games"
_TABLE_SHOT_EVENTS = "shot_events"
_TABLE_GAME_CONTEXT = "game_context"
_TABLE_COLLECTION_LOG = "collection_log"


def _table_exists(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _count_rows(conn, table_name, where_clause=None):
    if not _table_exists(conn, table_name):
        return 0

    query = f"SELECT COUNT(*) FROM {table_name}"
    if where_clause:
        query = f"{query} WHERE {where_clause}"

    cursor = conn.cursor()
    cursor.execute(query)
    return cursor.fetchone()[0]


def _distinct_game_ids(conn, table_name):
    if not _table_exists(conn, table_name):
        return set()

    cursor = conn.cursor()
    cursor.execute(f"SELECT DISTINCT game_id FROM {table_name}")
    return {row[0] for row in cursor.fetchall() if row[0] is not None}


def _get_incomplete_collection_dates(conn):
    if not _table_exists(conn, _TABLE_COLLECTION_LOG):
        return 0

    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM collection_log WHERE completed_at IS NULL"
    )
    return cursor.fetchone()[0]


def _read_log_tail(log_path, tail_lines):
    if not os.path.exists(log_path):
        return []

    for encoding in _READ_ENCODINGS:
        try:
            with open(log_path, "r", encoding=encoding) as handle:
                lines = [line.rstrip() for line in handle.readlines()]
            return lines[-tail_lines:]
        except UnicodeError:
            continue

    with open(log_path, "r", errors="replace") as handle:
        lines = [line.rstrip() for line in handle.readlines()]
    return lines[-tail_lines:]


def build_status_report(log_path, tail_lines):
    conn = sqlite3.connect(DATABASE_PATH)

    raw_game_ids = set(get_collected_game_ids(conn))
    metadata_game_ids = _distinct_game_ids(conn, _TABLE_GAMES)
    shot_event_game_ids = _distinct_game_ids(conn, _TABLE_SHOT_EVENTS)
    game_context_ids = _distinct_game_ids(conn, _TABLE_GAME_CONTEXT)

    report = {
        "database_path": DATABASE_PATH,
        "database_size_mb": (
            os.path.getsize(DATABASE_PATH) / (1024 * 1024)
            if os.path.exists(DATABASE_PATH) else 0.0
        ),
        "raw_game_tables": len(raw_game_ids),
        "games_rows": _count_rows(conn, _TABLE_GAMES),
        "shot_events_rows": _count_rows(conn, _TABLE_SHOT_EVENTS),
        "shot_events_with_faceoff": _count_rows(
            conn, _TABLE_SHOT_EVENTS, "seconds_since_faceoff IS NOT NULL"
        ),
        "shot_events_with_zone": _count_rows(
            conn, _TABLE_SHOT_EVENTS, "faceoff_zone_code IS NOT NULL"
        ),
        "game_context_rows": _count_rows(conn, _TABLE_GAME_CONTEXT),
        "missing_metadata_games": len(raw_game_ids - metadata_game_ids),
        "missing_shot_event_games": len(raw_game_ids - shot_event_game_ids),
        "missing_game_context_games": len(metadata_game_ids - game_context_ids),
        "fully_processed_games": len(
            raw_game_ids & metadata_game_ids & shot_event_game_ids
        ),
        "last_completed_date": get_last_collected_date(conn),
        "incomplete_collection_dates": _get_incomplete_collection_dates(conn),
        "log_path": log_path,
        "log_exists": os.path.exists(log_path),
        "log_size_mb": (
            os.path.getsize(log_path) / (1024 * 1024)
            if os.path.exists(log_path) else 0.0
        ),
        "log_tail": _read_log_tail(log_path, tail_lines),
    }

    conn.close()
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Show progress for the NHL scrape/backfill database repair run."
    )
    parser.add_argument(
        "--log-path",
        default=os.path.join(_PROJECT_ROOT, _DEFAULT_LOG_FILENAME),
        help="Path to the backfill log file.",
    )
    parser.add_argument(
        "--tail-lines",
        type=int,
        default=_DEFAULT_TAIL_LINES,
        help="How many trailing log lines to print.",
    )
    args = parser.parse_args()

    report = build_status_report(args.log_path, args.tail_lines)

    print(f"Database: {report['database_path']}")
    print(f"Database size (MB): {report['database_size_mb']:.1f}")
    print(f"Raw game tables: {report['raw_game_tables']:,}")
    print(f"Games rows: {report['games_rows']:,}")
    print(f"Shot event rows: {report['shot_events_rows']:,}")
    print(f"Shot events with faceoff timing: {report['shot_events_with_faceoff']:,}")
    print(f"Shot events with zone code: {report['shot_events_with_zone']:,}")
    print(f"Game context rows: {report['game_context_rows']:,}")
    print(f"Fully processed games: {report['fully_processed_games']:,}")
    print(f"Missing metadata games: {report['missing_metadata_games']:,}")
    print(f"Missing shot-event games: {report['missing_shot_event_games']:,}")
    print(f"Missing game-context rows: {report['missing_game_context_games']:,}")
    print(f"Last completed collection date: {report['last_completed_date']}")
    print(f"Incomplete collection dates: {report['incomplete_collection_dates']:,}")
    print(f"Log file: {report['log_path']}")
    print(f"Log exists: {report['log_exists']}")
    print(f"Log size (MB): {report['log_size_mb']:.1f}")

    if report["log_tail"]:
        print("\nLatest log lines:")
        for line in report["log_tail"]:
            print(line)


if __name__ == "__main__":
    main()