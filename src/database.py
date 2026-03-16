# database.py

import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from sqlite3 import Error

DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATABASE_FILENAME = "nhl_data.db"
DATABASE_PATH = os.path.join(DATABASE_DIR, DATABASE_FILENAME)

_GAME_TABLE_PREFIX = "game_"
_VALID_POSITION_GROUPS = ("F", "D", "G")
_FEATURE_SET_VERSION = "v1"

# ── xG Phase 0: schema versions ──────────────────────────────────────

_XG_EVENT_SCHEMA_VERSION = "v2"
_XG_FEATURE_SCHEMA_VERSION = "v1"

# ── xG Phase 0: data-contract constants ──────────────────────────────

VALID_SHOT_TYPES = (
    "wrist",
    "slap",
    "snap",
    "backhand",
    "tip-in",
    "wrap-around",
    "deflection",
    "bat",
    "cradle",
    "poke",
)

VALID_MANPOWER_STATES = (
    "5v5",
    "5v4",
    "4v5",
    "5v3",
    "3v5",
    "4v4",
    "4v3",
    "3v4",
    "3v3",
    "6v5",
    "5v6",
    "6v4",
    "4v6",
    "6v3",
    "3v6",
)

VALID_SCORE_STATES = (
    "tied",
    "up1",
    "up2",
    "up3plus",
    "down1",
    "down2",
    "down3plus",
)

# NHL rink normalized coordinate bounds (feet)
NORMALIZED_X_COORD_MIN = -100.0
NORMALIZED_X_COORD_MAX = 100.0
NORMALIZED_Y_COORD_MIN = -42.5
NORMALIZED_Y_COORD_MAX = 42.5

_RAW_GAME_TABLE_COLUMNS = """\
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period INTEGER,
    time TEXT,
    event TEXT,
    description TEXT,
    UNIQUE(period, time, event, description)"""


def _quote_identifier(name):
    """Return a safely double-quoted SQLite identifier.

    Validates that the name contains only word characters (letters, digits,
    underscores) before quoting, preventing SQL injection via identifier names.
    """
    if not re.match(r'^\w+$', name):
        raise ValueError(f"Invalid identifier: {name!r}")
    return f'"{name}"'


def _game_table_name(game_id):
    return f"{_GAME_TABLE_PREFIX}{game_id}"


def create_table(conn, game_id):
    cursor = conn.cursor()
    quoted = _quote_identifier(_game_table_name(game_id))
    cursor.execute(f"CREATE TABLE IF NOT EXISTS {quoted} ({_RAW_GAME_TABLE_COLUMNS});")
    conn.commit()


def insert_data(conn, game_id, data_list):
    if not data_list:
        return
    cursor = conn.cursor()
    quoted = _quote_identifier(_game_table_name(game_id))
    columns = ', '.join(data_list[0].keys())
    placeholders = ', '.join(['?' for _ in data_list[0].keys()])
    insert_query = f"INSERT OR IGNORE INTO {quoted} ({columns}) VALUES ({placeholders})"
    cursor.executemany(insert_query, [tuple(d.values()) for d in data_list])
    conn.commit()


def create_collection_log_table(conn):
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS collection_log (
                        date TEXT PRIMARY KEY,
                        games_found INTEGER NOT NULL,
                        games_collected INTEGER NOT NULL,
                        completed_at TEXT
                      );""")
    conn.commit()


def is_game_collected(conn, game_id):
    table_name = _game_table_name(game_id)
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT 1 FROM {_quote_identifier(table_name)} LIMIT 1")
        return cursor.fetchone() is not None
    except sqlite3.OperationalError:
        return False


def mark_date_collected(conn, date_str, games_found, games_collected):
    cursor = conn.cursor()
    completed_at = datetime.now().isoformat() if games_collected >= games_found else None
    cursor.execute(
        "INSERT OR REPLACE INTO collection_log (date, games_found, games_collected, completed_at) "
        "VALUES (?, ?, ?, ?)",
        (date_str, games_found, games_collected, completed_at)
    )
    conn.commit()


def get_last_collected_date(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT MIN(date) FROM collection_log WHERE completed_at IS NULL")
    row = cursor.fetchone()
    if row and row[0]:
        return date.fromisoformat(row[0]) - timedelta(days=1)
    cursor.execute("SELECT MAX(date) FROM collection_log WHERE completed_at IS NOT NULL")
    row = cursor.fetchone()
    if row and row[0]:
        return date.fromisoformat(row[0])
    return None


def is_date_range_collected(conn, start_date, end_date):
    total_days = (end_date - start_date).days + 1
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM collection_log "
        "WHERE date >= ? AND date <= ? AND completed_at IS NOT NULL",
        (start_date.isoformat(), end_date.isoformat())
    )
    return cursor.fetchone()[0] == total_days


def fix_incomplete_collection_log(conn):
    """One-time migration: clear completed_at on rows where not all games were collected."""
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE collection_log SET completed_at = NULL "
        "WHERE games_collected < games_found AND completed_at IS NOT NULL"
    )
    if cursor.rowcount > 0:
        print(f"Fixed {cursor.rowcount} incomplete collection_log entries")
    conn.commit()


def deduplicate_existing_tables(conn):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name LIKE ?",
        (f"{_GAME_TABLE_PREFIX}%",)
    )

    for table_name, create_sql in cursor.fetchall():
        if "UNIQUE(period, time, event, description)" in create_sql:
            continue

        print(f"Deduplicating and migrating {table_name}...")
        temp_name = f"{table_name}_dedup_tmp"
        quoted = _quote_identifier(table_name)
        quoted_temp = _quote_identifier(temp_name)
        cursor.execute(f"CREATE TABLE {quoted_temp} ({_RAW_GAME_TABLE_COLUMNS})")
        cursor.execute(
            f"INSERT OR IGNORE INTO {quoted_temp} (period, time, event, description) "
            f"SELECT period, time, event, description FROM {quoted}"
        )
        cursor.execute(f"DROP TABLE {quoted}")
        cursor.execute(f"ALTER TABLE {quoted_temp} RENAME TO {quoted}")

    conn.commit()


def create_core_dimension_tables(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS players (
            player_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            shoots_catches TEXT,
            position TEXT,
            team_id INTEGER
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS games (
            game_id INTEGER PRIMARY KEY,
            game_date TEXT,
            season TEXT,
            home_team_id INTEGER,
            away_team_id INTEGER
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER PRIMARY KEY,
            team_abbrev TEXT,
            team_name TEXT
        )
        """
    )
    conn.commit()


def create_player_game_stats_table(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS player_game_stats (
            player_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            team_id INTEGER,
            position_group TEXT NOT NULL,
            toi_seconds INTEGER NOT NULL DEFAULT 0,
            goals INTEGER NOT NULL DEFAULT 0,
            assists INTEGER NOT NULL DEFAULT 0,
            shots INTEGER NOT NULL DEFAULT 0,
            blocks INTEGER NOT NULL DEFAULT 0,
            hits INTEGER NOT NULL DEFAULT 0,
            penalties_drawn INTEGER NOT NULL DEFAULT 0,
            penalties_taken INTEGER NOT NULL DEFAULT 0,
            faceoff_wins INTEGER NOT NULL DEFAULT 0,
            faceoff_losses INTEGER NOT NULL DEFAULT 0,
            xgf REAL NOT NULL DEFAULT 0,
            xga REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (player_id, game_id)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_player_game_stats_game_id ON player_game_stats(game_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_player_game_stats_position_group_game_id ON player_game_stats(position_group, game_id)"
    )
    conn.commit()


def create_player_game_features_table(conn):
    cursor = conn.cursor()
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS player_game_features (
            player_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            season TEXT,
            game_number_for_player INTEGER,
            toi_rank_pos_5g REAL,
            toi_rank_pos_10g REAL,
            toi_rolling_mean_5g REAL,
            points_rolling_10g REAL,
            feature_set_version TEXT DEFAULT '{_FEATURE_SET_VERSION}',
            PRIMARY KEY (player_id, game_id)
        )
        """
    )
    conn.commit()


def validate_player_game_stats_quality(conn, max_toi_seconds=3600):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT player_id, game_id, COUNT(*) AS row_count
            FROM player_game_stats
            GROUP BY player_id, game_id
            HAVING COUNT(*) > 1
        )
        """
    )
    duplicate_player_game_rows = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM player_game_stats WHERE toi_seconds < 0")
    negative_toi_rows = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM player_game_stats WHERE toi_seconds > ?", (max_toi_seconds,))
    toi_above_max_rows = cursor.fetchone()[0]

    position_placeholders = ', '.join(['?' for _ in _VALID_POSITION_GROUPS])
    cursor.execute(
        f"SELECT COUNT(*) FROM player_game_stats WHERE position_group NOT IN ({position_placeholders})",
        _VALID_POSITION_GROUPS
    )
    invalid_position_group_rows = cursor.fetchone()[0]

    return {
        "duplicate_player_game_rows": duplicate_player_game_rows,
        "negative_toi_rows": negative_toi_rows,
        "toi_above_max_rows": toi_above_max_rows,
        "invalid_position_group_rows": invalid_position_group_rows,
    }


def ensure_player_database_schema(conn):
    create_core_dimension_tables(conn)
    create_player_game_stats_table(conn)
    create_player_game_features_table(conn)


# ── xG Phase 0: canonical shot events table ──────────────────────────

def create_shot_events_table(conn):
    cursor = conn.cursor()
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS shot_events (
            shot_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            event_idx INTEGER NOT NULL,
            period INTEGER NOT NULL,
            time_in_period TEXT NOT NULL,
            time_remaining_seconds INTEGER NOT NULL,
            shot_type TEXT NOT NULL,
            x_coord REAL,
            y_coord REAL,
            distance_to_goal REAL,
            angle_to_goal REAL,
            is_goal INTEGER NOT NULL DEFAULT 0,
            shooting_team_id INTEGER NOT NULL,
            goalie_id INTEGER,
            shooter_id INTEGER,
            score_state TEXT,
            manpower_state TEXT,
            seconds_since_faceoff INTEGER,
            faceoff_zone_code TEXT,
            event_schema_version TEXT NOT NULL DEFAULT '{_XG_EVENT_SCHEMA_VERSION}',
            UNIQUE(game_id, event_idx)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_shot_events_game_id "
        "ON shot_events(game_id)"
    )
    conn.commit()


def validate_shot_events_quality(conn):
    cursor = conn.cursor()

    shot_type_placeholders = ", ".join(["?"] * len(VALID_SHOT_TYPES))
    cursor.execute(
        f"SELECT COUNT(*) FROM shot_events "
        f"WHERE shot_type NOT IN ({shot_type_placeholders})",
        VALID_SHOT_TYPES,
    )
    invalid_shot_type_rows = cursor.fetchone()[0]

    manpower_placeholders = ", ".join(["?"] * len(VALID_MANPOWER_STATES))
    cursor.execute(
        f"SELECT COUNT(*) FROM shot_events "
        f"WHERE manpower_state IS NOT NULL "
        f"AND manpower_state NOT IN ({manpower_placeholders})",
        VALID_MANPOWER_STATES,
    )
    invalid_manpower_state_rows = cursor.fetchone()[0]

    score_placeholders = ", ".join(["?"] * len(VALID_SCORE_STATES))
    cursor.execute(
        f"SELECT COUNT(*) FROM shot_events "
        f"WHERE score_state IS NOT NULL "
        f"AND score_state NOT IN ({score_placeholders})",
        VALID_SCORE_STATES,
    )
    invalid_score_state_rows = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM shot_events "
        "WHERE x_coord IS NOT NULL AND (x_coord < ? OR x_coord > ?)",
        (NORMALIZED_X_COORD_MIN, NORMALIZED_X_COORD_MAX),
    )
    x_coord_out_of_range_rows = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM shot_events "
        "WHERE y_coord IS NOT NULL AND (y_coord < ? OR y_coord > ?)",
        (NORMALIZED_Y_COORD_MIN, NORMALIZED_Y_COORD_MAX),
    )
    y_coord_out_of_range_rows = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM shot_events WHERE is_goal NOT IN (0, 1)"
    )
    invalid_is_goal_rows = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM shot_events WHERE time_remaining_seconds < 0"
    )
    negative_time_remaining_rows = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT game_id, event_idx, COUNT(*) AS row_count
            FROM shot_events
            GROUP BY game_id, event_idx
            HAVING COUNT(*) > 1
        )
        """
    )
    duplicate_game_event_rows = cursor.fetchone()[0]

    return {
        "invalid_shot_type_rows": invalid_shot_type_rows,
        "invalid_manpower_state_rows": invalid_manpower_state_rows,
        "invalid_score_state_rows": invalid_score_state_rows,
        "x_coord_out_of_range_rows": x_coord_out_of_range_rows,
        "y_coord_out_of_range_rows": y_coord_out_of_range_rows,
        "invalid_is_goal_rows": invalid_is_goal_rows,
        "negative_time_remaining_rows": negative_time_remaining_rows,
        "duplicate_game_event_rows": duplicate_game_event_rows,
    }


def _migrate_shot_events_v1_to_v2(conn):
    """Add seconds_since_faceoff and faceoff_zone_code columns if missing."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(shot_events)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    if "seconds_since_faceoff" not in existing_cols:
        cursor.execute(
            "ALTER TABLE shot_events ADD COLUMN seconds_since_faceoff INTEGER"
        )
    if "faceoff_zone_code" not in existing_cols:
        cursor.execute(
            "ALTER TABLE shot_events ADD COLUMN faceoff_zone_code TEXT"
        )
    conn.commit()


_SHOT_EVENTS_INSERT_COLUMNS = (
    "game_id", "event_idx", "period", "time_in_period",
    "time_remaining_seconds", "shot_type", "x_coord", "y_coord",
    "distance_to_goal", "angle_to_goal", "is_goal",
    "shooting_team_id", "goalie_id", "shooter_id",
    "score_state", "manpower_state",
    "seconds_since_faceoff", "faceoff_zone_code",
    "event_schema_version",
)

_SHOT_EVENTS_ALLOWED_KEYS = frozenset(_SHOT_EVENTS_INSERT_COLUMNS)


def insert_shot_events(conn, shot_event_dicts):
    """Insert shot event dicts into shot_events table using executemany.

    Keys are validated against an allowlist. event_schema_version is
    auto-populated if not present. Duplicates are silently ignored.
    """
    if not shot_event_dicts:
        return

    for d in shot_event_dicts:
        bad_keys = set(d.keys()) - _SHOT_EVENTS_ALLOWED_KEYS
        if bad_keys:
            raise ValueError(f"Invalid shot event keys: {bad_keys}")

    cols = ", ".join(_SHOT_EVENTS_INSERT_COLUMNS)
    placeholders = ", ".join(["?"] * len(_SHOT_EVENTS_INSERT_COLUMNS))
    query = f"INSERT OR IGNORE INTO shot_events ({cols}) VALUES ({placeholders})"

    rows = [
        tuple(
            d.get(c, _XG_EVENT_SCHEMA_VERSION) if c == "event_schema_version"
            else d.get(c)
            for c in _SHOT_EVENTS_INSERT_COLUMNS
        )
        for d in shot_event_dicts
    ]

    cursor = conn.cursor()
    cursor.executemany(query, rows)
    conn.commit()


def game_has_shot_events(conn, game_id):
    """Return True if shot_events contains at least one row for game_id."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM shot_events WHERE game_id = ? LIMIT 1", (game_id,)
    )
    return cursor.fetchone() is not None


def ensure_xg_schema(conn):
    create_shot_events_table(conn)
    _migrate_shot_events_v1_to_v2(conn)


def create_connection(database_file):
    """
    Create a database connection to the SQLite database specified by the database_file
    :param database_file: database file
    :return: Connection object or None
    """
    conn = None
    try:
        conn = sqlite3.connect(database_file)
        print(f"SQLite connection established to {database_file}")
    except Error as e:
        print(e)

    return conn
