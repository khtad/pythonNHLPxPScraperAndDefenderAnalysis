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
_GAME_ID_SUFFIX_START = len(_GAME_TABLE_PREFIX)
_SQLITE_TABLE_TYPE = "table"
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


def _is_raw_game_table_name(table_name):
    if not table_name.startswith(_GAME_TABLE_PREFIX):
        return False
    return table_name[_GAME_ID_SUFFIX_START:].isdigit()


def get_collected_game_ids(conn):
    """Return sorted game IDs for collected raw game tables."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = ? AND name LIKE ? ORDER BY name",
        (_SQLITE_TABLE_TYPE, f"{_GAME_TABLE_PREFIX}%"),
    )

    game_ids = []
    for (table_name,) in cursor.fetchall():
        if _is_raw_game_table_name(table_name):
            game_ids.append(int(table_name[_GAME_ID_SUFFIX_START:]))
    return game_ids


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
        if not _is_raw_game_table_name(table_name):
            continue
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
            away_team_id INTEGER,
            venue_name TEXT,
            venue_city TEXT,
            venue_utc_offset TEXT
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


def game_has_metadata(conn, game_id):
    """Return True if the games table has a row for game_id."""
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM games WHERE game_id = ? LIMIT 1", (game_id,))
    return cursor.fetchone() is not None


def upsert_game_metadata(conn, game_id, game_date, season,
                         home_team_id, away_team_id,
                         venue_name=None, venue_city=None,
                         venue_utc_offset=None):
    """Insert or update a row in the games dimension table."""
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO games (game_id, game_date, season,
                              home_team_id, away_team_id,
                              venue_name, venue_city, venue_utc_offset)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(game_id) DO UPDATE SET
               game_date = excluded.game_date,
               season = excluded.season,
               home_team_id = excluded.home_team_id,
               away_team_id = excluded.away_team_id,
               venue_name = excluded.venue_name,
               venue_city = excluded.venue_city,
               venue_utc_offset = excluded.venue_utc_offset""",
        (game_id, game_date, season, home_team_id, away_team_id,
         venue_name, venue_city, venue_utc_offset),
    )
    conn.commit()


def upsert_team(conn, team_id, abbrev, name):
    """Insert or update a row in the teams dimension table."""
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO teams (team_id, team_abbrev, team_name)
           VALUES (?, ?, ?)
           ON CONFLICT(team_id) DO UPDATE SET
               team_abbrev = excluded.team_abbrev,
               team_name = excluded.team_name""",
        (team_id, abbrev, name),
    )
    conn.commit()


# ── Phase 2, Area 1: game_context table ─────────────────────────────

_GAME_CONTEXT_SCHEMA_VERSION = "v1"


def create_game_context_table(conn):
    """Create the game_context table for rest/travel comparative features."""
    cursor = conn.cursor()
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS game_context (
            game_id INTEGER PRIMARY KEY,
            home_rest_days INTEGER,
            away_rest_days INTEGER,
            rest_advantage INTEGER,
            home_is_back_to_back INTEGER,
            away_is_back_to_back INTEGER,
            travel_distance_km REAL,
            timezone_delta REAL,
            context_schema_version TEXT NOT NULL
                DEFAULT '{_GAME_CONTEXT_SCHEMA_VERSION}'
        )
        """
    )
    conn.commit()


def game_has_context(conn, game_id):
    """Return True if game_context has a row for game_id."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM game_context WHERE game_id = ? LIMIT 1", (game_id,)
    )
    return cursor.fetchone() is not None


def _get_previous_game_date(conn, team_id, game_date, game_id):
    """Return the most recent game_date for team_id before game_date, or None."""
    cursor = conn.cursor()
    cursor.execute(
        """SELECT game_date FROM games
           WHERE (home_team_id = ? OR away_team_id = ?)
             AND game_date < ?
             AND game_id != ?
           ORDER BY game_date DESC LIMIT 1""",
        (team_id, team_id, game_date, game_id),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def populate_game_context(conn, game_id):
    """Compute and insert rest/travel context for a single game.

    Queries games table for schedule info and arena_reference for locations.
    Skips if game_context row already exists for game_id.
    """
    if game_has_context(conn, game_id):
        return

    cursor = conn.cursor()
    cursor.execute(
        "SELECT game_date, home_team_id, away_team_id "
        "FROM games WHERE game_id = ?",
        (game_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return

    game_date, home_team_id, away_team_id = row

    from xg_features import compute_rest_days, is_back_to_back, haversine_distance, compute_timezone_delta
    from arena_reference import get_arena_info

    # Rest days
    home_prev = _get_previous_game_date(conn, home_team_id, game_date, game_id)
    away_prev = _get_previous_game_date(conn, away_team_id, game_date, game_id)

    home_rest = compute_rest_days(game_date, home_prev)
    away_rest = compute_rest_days(game_date, away_prev)

    rest_advantage = (home_rest - away_rest) if (home_rest is not None and away_rest is not None) else None
    home_b2b = is_back_to_back(home_rest)
    away_b2b = is_back_to_back(away_rest)

    # Travel distance and timezone delta
    home_arena = get_arena_info(home_team_id)
    away_arena = get_arena_info(away_team_id)

    if home_arena and away_arena:
        travel_dist = haversine_distance(
            away_arena["lat"], away_arena["lon"],
            home_arena["lat"], home_arena["lon"],
        )
        tz_delta = compute_timezone_delta(
            away_arena["timezone_utc_offset"],
            home_arena["timezone_utc_offset"],
        )
    else:
        travel_dist = None
        tz_delta = None

    cursor.execute(
        """INSERT OR IGNORE INTO game_context
           (game_id, home_rest_days, away_rest_days, rest_advantage,
            home_is_back_to_back, away_is_back_to_back,
            travel_distance_km, timezone_delta, context_schema_version)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (game_id, home_rest, away_rest, rest_advantage,
         home_b2b, away_b2b, travel_dist, tz_delta,
         _GAME_CONTEXT_SCHEMA_VERSION),
    )
    conn.commit()


# ── Phase 2, Area 4: venue bias diagnostics ─────────────────────────


def create_venue_bias_diagnostics_table(conn):
    """Create the venue_bias_diagnostics table."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS venue_bias_diagnostics (
            venue_name TEXT NOT NULL,
            season TEXT NOT NULL,
            total_shots INTEGER,
            avg_distance REAL,
            x_coord_mean REAL,
            x_coord_stddev REAL,
            y_coord_mean REAL,
            y_coord_stddev REAL,
            shot_count_z_score REAL,
            distance_z_score REAL,
            bias_flag INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (venue_name, season)
        )
        """
    )
    conn.commit()


def _migrate_games_add_venue_columns(conn):
    """Add venue_name, venue_city, venue_utc_offset columns to games if missing."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='games'"
    )
    if cursor.fetchone() is None:
        return
    cursor.execute("PRAGMA table_info(games)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    if "venue_name" not in existing_cols:
        cursor.execute("ALTER TABLE games ADD COLUMN venue_name TEXT")
    if "venue_city" not in existing_cols:
        cursor.execute("ALTER TABLE games ADD COLUMN venue_city TEXT")
    if "venue_utc_offset" not in existing_cols:
        cursor.execute("ALTER TABLE games ADD COLUMN venue_utc_offset TEXT")
    conn.commit()


def compute_venue_season_stats(conn, venue_name, season):
    """Compute shot statistics for a venue in a given season.

    Returns dict with total_shots, avg_distance, x/y coord mean/stddev.
    Standard deviation is computed in Python since SQLite lacks STDEV().
    """
    cursor = conn.cursor()
    cursor.execute(
        """SELECT se.distance_to_goal, se.x_coord, se.y_coord
           FROM shot_events se
           JOIN games g ON se.game_id = g.game_id
           WHERE g.venue_name = ? AND g.season = ?
             AND se.x_coord IS NOT NULL
             AND se.y_coord IS NOT NULL""",
        (venue_name, season),
    )
    rows = cursor.fetchall()

    if not rows:
        return {
            "total_shots": 0,
            "avg_distance": None,
            "x_coord_mean": None,
            "x_coord_stddev": None,
            "y_coord_mean": None,
            "y_coord_stddev": None,
        }

    distances = [r[0] for r in rows if r[0] is not None]
    x_coords = [r[1] for r in rows]
    y_coords = [r[2] for r in rows]

    total = len(rows)
    avg_dist = sum(distances) / len(distances) if distances else None

    x_mean = sum(x_coords) / total
    y_mean = sum(y_coords) / total

    x_stddev = _stddev(x_coords, x_mean)
    y_stddev = _stddev(y_coords, y_mean)

    return {
        "total_shots": total,
        "avg_distance": avg_dist,
        "x_coord_mean": x_mean,
        "x_coord_stddev": x_stddev,
        "y_coord_mean": y_mean,
        "y_coord_stddev": y_stddev,
    }


def compute_league_season_stats(conn, season):
    """Compute league-wide shot statistics for a season.

    Returns dict with total_shots, avg_distance, x/y coord mean/stddev,
    plus per-venue shot count mean/stddev for z-score computation.
    """
    cursor = conn.cursor()
    cursor.execute(
        """SELECT se.distance_to_goal, se.x_coord, se.y_coord
           FROM shot_events se
           JOIN games g ON se.game_id = g.game_id
           WHERE g.season = ?
             AND se.x_coord IS NOT NULL
             AND se.y_coord IS NOT NULL""",
        (season,),
    )
    rows = cursor.fetchall()

    if not rows:
        return {
            "total_shots": 0,
            "avg_distance": None,
            "avg_distance_stddev": None,
            "x_coord_mean": None,
            "y_coord_mean": None,
            "venue_shot_count_mean": None,
            "venue_shot_count_stddev": None,
            "venue_avg_distance_mean": None,
            "venue_avg_distance_stddev": None,
        }

    distances = [r[0] for r in rows if r[0] is not None]
    x_coords = [r[1] for r in rows]
    y_coords = [r[2] for r in rows]

    total = len(rows)
    avg_dist = sum(distances) / len(distances) if distances else None

    # Per-venue aggregates for z-score denominators
    cursor.execute(
        """SELECT g.venue_name, COUNT(*) as cnt,
                  AVG(se.distance_to_goal) as avg_d
           FROM shot_events se
           JOIN games g ON se.game_id = g.game_id
           WHERE g.season = ? AND g.venue_name IS NOT NULL
             AND se.x_coord IS NOT NULL
           GROUP BY g.venue_name""",
        (season,),
    )
    venue_rows = cursor.fetchall()
    venue_counts = [r[1] for r in venue_rows]
    venue_avg_dists = [r[2] for r in venue_rows if r[2] is not None]

    vc_mean = sum(venue_counts) / len(venue_counts) if venue_counts else None
    vc_stddev = _stddev(venue_counts, vc_mean) if vc_mean is not None else None

    vd_mean = sum(venue_avg_dists) / len(venue_avg_dists) if venue_avg_dists else None
    vd_stddev = _stddev(venue_avg_dists, vd_mean) if vd_mean is not None else None

    return {
        "total_shots": total,
        "avg_distance": avg_dist,
        "x_coord_mean": sum(x_coords) / total,
        "y_coord_mean": sum(y_coords) / total,
        "venue_shot_count_mean": vc_mean,
        "venue_shot_count_stddev": vc_stddev,
        "venue_avg_distance_mean": vd_mean,
        "venue_avg_distance_stddev": vd_stddev,
    }


_VENUE_BIAS_Z_SCORE_THRESHOLD = 2.0


def populate_venue_diagnostics(conn, season):
    """Compute and insert venue bias diagnostics for all venues in a season."""
    league = compute_league_season_stats(conn, season)
    if league["total_shots"] == 0:
        return

    cursor = conn.cursor()
    cursor.execute(
        """SELECT DISTINCT g.venue_name FROM games g
           WHERE g.season = ? AND g.venue_name IS NOT NULL""",
        (season,),
    )
    venues = [r[0] for r in cursor.fetchall()]

    for venue_name in venues:
        stats = compute_venue_season_stats(conn, venue_name, season)
        if stats["total_shots"] == 0:
            continue

        # Z-scores
        sc_z = None
        if league["venue_shot_count_stddev"] and league["venue_shot_count_stddev"] > 0:
            sc_z = (
                (stats["total_shots"] - league["venue_shot_count_mean"])
                / league["venue_shot_count_stddev"]
            )

        dist_z = None
        if (league["venue_avg_distance_stddev"]
                and league["venue_avg_distance_stddev"] > 0
                and stats["avg_distance"] is not None):
            dist_z = (
                (stats["avg_distance"] - league["venue_avg_distance_mean"])
                / league["venue_avg_distance_stddev"]
            )

        bias_flag = 0
        if sc_z is not None and abs(sc_z) > _VENUE_BIAS_Z_SCORE_THRESHOLD:
            bias_flag = 1
        if dist_z is not None and abs(dist_z) > _VENUE_BIAS_Z_SCORE_THRESHOLD:
            bias_flag = 1

        cursor.execute(
            """INSERT OR REPLACE INTO venue_bias_diagnostics
               (venue_name, season, total_shots, avg_distance,
                x_coord_mean, x_coord_stddev, y_coord_mean, y_coord_stddev,
                shot_count_z_score, distance_z_score, bias_flag)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (venue_name, season, stats["total_shots"], stats["avg_distance"],
             stats["x_coord_mean"], stats["x_coord_stddev"],
             stats["y_coord_mean"], stats["y_coord_stddev"],
             sc_z, dist_z, bias_flag),
        )

    conn.commit()


def _stddev(values, mean):
    """Compute population standard deviation given values and their mean."""
    if not values or len(values) < 2:
        return 0.0
    import math
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def ensure_xg_schema(conn):
    create_shot_events_table(conn)
    _migrate_shot_events_v1_to_v2(conn)
    _migrate_games_add_venue_columns(conn)
    create_game_context_table(conn)
    create_venue_bias_diagnostics_table(conn)


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
