# database.py

import os
import random
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

_XG_EVENT_SCHEMA_VERSION = "v4"
_XG_FEATURE_SCHEMA_VERSION = "v1"
_SHIFT_SCHEMA_VERSION = "v1"
_ON_ICE_SCHEMA_VERSION = "v1"

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


_IDENTIFIER_RE = re.compile(r'^\w+$')


def _quote_identifier(name):
    """Return a safely double-quoted SQLite identifier.

    Validates that the name contains only word characters (letters, digits,
    underscores) before quoting, preventing SQL injection via identifier names.
    """
    if not _IDENTIFIER_RE.match(name):
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


def load_game_shots(conn, game_id):
    """Return all shots for game_id as a list of dicts, ordered by event_idx.

    Each dict contains every shot_events column plus game_date, season,
    home_team_id, away_team_id, and venue_name from the games dimension.
    """
    cursor = conn.cursor()
    cursor.execute(
        """SELECT se.*,
                  g.game_date, g.season,
                  g.home_team_id, g.away_team_id, g.venue_name
           FROM shot_events se
           JOIN games g ON se.game_id = g.game_id
           WHERE se.game_id = ?
           ORDER BY se.event_idx""",
        (game_id,),
    )
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _eligible_random_games_sql(include_season_filter):
    season_clause = "AND g.season = ?" if include_season_filter else ""
    return f"""
        SELECT g.game_id FROM games g
        WHERE (
            SELECT COUNT(*) FROM shot_events se
            WHERE se.game_id = g.game_id
              AND se.event_schema_version = ?
        ) >= ?
        {season_clause}
    """


def get_random_game_id(conn, season=None, min_shots=1, seed=None):
    """Return a random game_id whose shots are at the current schema version.

    season: optional season filter (coerced via str()).
    min_shots: minimum shot_events rows at the current schema version
        required for a game to be eligible.
    seed: when set, picks a deterministic offset via a local random.Random
        so multiple calls with the same seed return the same game_id.
    Returns None when no game meets the criteria.
    """
    cursor = conn.cursor()
    season_filter = str(season) if season is not None else None
    has_season = season_filter is not None

    eligible_sql = _eligible_random_games_sql(has_season)
    params = [_XG_EVENT_SCHEMA_VERSION, min_shots]
    if has_season:
        params.append(season_filter)

    if seed is None:
        cursor.execute(eligible_sql + " ORDER BY RANDOM() LIMIT 1", params)
        row = cursor.fetchone()
        return row[0] if row else None

    count_sql = f"SELECT COUNT(*) FROM ({eligible_sql})"
    cursor.execute(count_sql, params)
    (n_candidates,) = cursor.fetchone()
    if n_candidates == 0:
        return None

    rng = random.Random(seed)
    offset = rng.randrange(n_candidates)
    cursor.execute(
        eligible_sql + " ORDER BY g.game_id LIMIT 1 OFFSET ?", params + [offset]
    )
    row = cursor.fetchone()
    return row[0] if row else None


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
    columns = ', '.join(_quote_identifier(k) for k in data_list[0].keys())
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


class PlayerMetadataNotFound(LookupError):
    """Upstream player-metadata source has no record for this player_id
    (e.g., a 404 from the NHL player-landing endpoint for a pre-modern
    player). Callers should cache this outcome via
    `mark_players_metadata_unavailable` so future runs skip the id
    instead of re-hitting the API every scrape.
    """

    def __init__(self, player_id):
        super().__init__(f"No upstream metadata for player_id={player_id}")
        self.player_id = player_id


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


def _count_invalid_enum(cursor, table, column, valid_values, nullable=False):
    """Count rows where column holds a value outside the valid set."""
    quoted_table = _quote_identifier(table)
    quoted_col = _quote_identifier(column)
    placeholders = ", ".join(["?"] * len(valid_values))
    null_guard = f"{quoted_col} IS NOT NULL AND " if nullable else ""
    cursor.execute(
        f"SELECT COUNT(*) FROM {quoted_table} "
        f"WHERE {null_guard}{quoted_col} NOT IN ({placeholders})",
        valid_values,
    )
    return cursor.fetchone()[0]


def _count_duplicates(cursor, table, key_columns):
    """Count rows with duplicate composite keys."""
    quoted_table = _quote_identifier(table)
    cols = ", ".join(_quote_identifier(c) for c in key_columns)
    cursor.execute(
        f"SELECT COUNT(*) FROM ("
        f"SELECT {cols}, COUNT(*) AS n FROM {quoted_table} "
        f"GROUP BY {cols} HAVING COUNT(*) > 1)"
    )
    return cursor.fetchone()[0]


def _count_negative(cursor, table, column):
    """Count rows where column < 0."""
    cursor.execute(
        f"SELECT COUNT(*) FROM {_quote_identifier(table)} "
        f"WHERE {_quote_identifier(column)} < 0"
    )
    return cursor.fetchone()[0]


def _count_above_max(cursor, table, column, max_val):
    """Count rows where column > max_val."""
    cursor.execute(
        f"SELECT COUNT(*) FROM {_quote_identifier(table)} "
        f"WHERE {_quote_identifier(column)} > ?",
        (max_val,),
    )
    return cursor.fetchone()[0]


def _count_out_of_range(cursor, table, column, min_val, max_val):
    """Count rows where a nullable numeric column is outside [min, max]."""
    quoted_col = _quote_identifier(column)
    cursor.execute(
        f"SELECT COUNT(*) FROM {_quote_identifier(table)} "
        f"WHERE {quoted_col} IS NOT NULL AND ({quoted_col} < ? OR {quoted_col} > ?)",
        (min_val, max_val),
    )
    return cursor.fetchone()[0]


def validate_player_game_stats_quality(conn, max_toi_seconds=3600):
    cursor = conn.cursor()
    return {
        "duplicate_player_game_rows": _count_duplicates(
            cursor, "player_game_stats", ("player_id", "game_id")),
        "negative_toi_rows": _count_negative(
            cursor, "player_game_stats", "toi_seconds"),
        "toi_above_max_rows": _count_above_max(
            cursor, "player_game_stats", "toi_seconds", max_toi_seconds),
        "invalid_position_group_rows": _count_invalid_enum(
            cursor, "player_game_stats", "position_group", _VALID_POSITION_GROUPS),
    }


def create_player_metadata_unavailable_table(conn):
    """Tracks player_ids that the upstream metadata endpoint has no record for,
    so the backfill loop can skip them instead of re-hitting the API every run.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS player_metadata_unavailable (
            player_id INTEGER PRIMARY KEY,
            attempted_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def mark_players_metadata_unavailable(conn, player_ids):
    """Record a batch of player_ids as permanently missing upstream metadata.

    Idempotent: a second call for the same id bumps `attempted_at` to the
    latest attempt timestamp.
    """
    if not player_ids:
        return
    attempted_at = datetime.now().isoformat()
    rows = [(player_id, attempted_at) for player_id in player_ids]
    cursor = conn.cursor()
    cursor.executemany(
        """INSERT INTO player_metadata_unavailable (player_id, attempted_at)
           VALUES (?, ?)
           ON CONFLICT(player_id) DO UPDATE SET attempted_at = excluded.attempted_at""",
        rows,
    )
    conn.commit()


def ensure_player_database_schema(conn):
    create_core_dimension_tables(conn)
    create_player_game_stats_table(conn)
    create_player_game_features_table(conn)
    create_player_metadata_unavailable_table(conn)


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
            home_on_ice_1_player_id INTEGER,
            home_on_ice_2_player_id INTEGER,
            home_on_ice_3_player_id INTEGER,
            home_on_ice_4_player_id INTEGER,
            home_on_ice_5_player_id INTEGER,
            home_on_ice_6_player_id INTEGER,
            away_on_ice_1_player_id INTEGER,
            away_on_ice_2_player_id INTEGER,
            away_on_ice_3_player_id INTEGER,
            away_on_ice_4_player_id INTEGER,
            away_on_ice_5_player_id INTEGER,
            away_on_ice_6_player_id INTEGER,
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


_VALID_IS_GOAL_VALUES = (0, 1)


def validate_shot_events_quality(conn):
    cursor = conn.cursor()
    _t = "shot_events"
    return {
        "invalid_shot_type_rows": _count_invalid_enum(
            cursor, _t, "shot_type", VALID_SHOT_TYPES),
        "invalid_manpower_state_rows": _count_invalid_enum(
            cursor, _t, "manpower_state", VALID_MANPOWER_STATES, nullable=True),
        "invalid_score_state_rows": _count_invalid_enum(
            cursor, _t, "score_state", VALID_SCORE_STATES, nullable=True),
        "x_coord_out_of_range_rows": _count_out_of_range(
            cursor, _t, "x_coord", NORMALIZED_X_COORD_MIN, NORMALIZED_X_COORD_MAX),
        "y_coord_out_of_range_rows": _count_out_of_range(
            cursor, _t, "y_coord", NORMALIZED_Y_COORD_MIN, NORMALIZED_Y_COORD_MAX),
        "invalid_is_goal_rows": _count_invalid_enum(
            cursor, _t, "is_goal", _VALID_IS_GOAL_VALUES),
        "negative_time_remaining_rows": _count_negative(
            cursor, _t, "time_remaining_seconds"),
        "duplicate_game_event_rows": _count_duplicates(
            cursor, _t, ("game_id", "event_idx")),
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


_SHOT_EVENTS_ON_ICE_COLUMNS = (
    "home_on_ice_1_player_id",
    "home_on_ice_2_player_id",
    "home_on_ice_3_player_id",
    "home_on_ice_4_player_id",
    "home_on_ice_5_player_id",
    "home_on_ice_6_player_id",
    "away_on_ice_1_player_id",
    "away_on_ice_2_player_id",
    "away_on_ice_3_player_id",
    "away_on_ice_4_player_id",
    "away_on_ice_5_player_id",
    "away_on_ice_6_player_id",
)


def _migrate_shot_events_v3_to_v4(conn):
    """Add on-ice player slots used by roster-change decomposition phases."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(shot_events)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    for column_name in _SHOT_EVENTS_ON_ICE_COLUMNS:
        if column_name not in existing_cols:
            cursor.execute(
                f"ALTER TABLE shot_events ADD COLUMN {_quote_identifier(column_name)} INTEGER"
            )
    conn.commit()


_SHOT_EVENTS_INSERT_COLUMNS = (
    "game_id", "event_idx", "period", "time_in_period",
    "time_remaining_seconds", "shot_type", "x_coord", "y_coord",
    "distance_to_goal", "angle_to_goal", "is_goal",
    "shooting_team_id", "goalie_id", "shooter_id",
    "score_state", "manpower_state",
    "seconds_since_faceoff", "faceoff_zone_code",
    "home_on_ice_1_player_id", "home_on_ice_2_player_id",
    "home_on_ice_3_player_id", "home_on_ice_4_player_id",
    "home_on_ice_5_player_id", "home_on_ice_6_player_id",
    "away_on_ice_1_player_id", "away_on_ice_2_player_id",
    "away_on_ice_3_player_id", "away_on_ice_4_player_id",
    "away_on_ice_5_player_id", "away_on_ice_6_player_id",
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


def game_has_current_shot_events(conn, game_id):
    """Return True if shot_events has rows for game_id at the current schema version."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM shot_events "
        "WHERE game_id = ? AND event_schema_version = ? LIMIT 1",
        (game_id, _XG_EVENT_SCHEMA_VERSION),
    )
    return cursor.fetchone() is not None


def delete_game_shot_events(conn, game_id):
    """Delete all shot_events rows for a game (used before re-ingesting stale data)."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM shot_events WHERE game_id = ?", (game_id,))
    conn.commit()


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


_PLAYERS_INSERT_COLUMNS = (
    "player_id",
    "first_name",
    "last_name",
    "shoots_catches",
    "position",
    "team_id",
)

_PLAYERS_ALLOWED_KEYS = frozenset(_PLAYERS_INSERT_COLUMNS)

_PLAYERS_UPSERT_SQL = (
    "INSERT INTO players (player_id, first_name, last_name, "
    "shoots_catches, position, team_id) "
    "VALUES (?, ?, ?, ?, ?, ?) "
    "ON CONFLICT(player_id) DO UPDATE SET "
    "first_name = excluded.first_name, "
    "last_name = excluded.last_name, "
    "shoots_catches = excluded.shoots_catches, "
    "position = excluded.position, "
    "team_id = excluded.team_id"
)

_NHL_FORWARD_POSITIONS = ("C", "L", "R")
_NHL_DEFENSE_POSITIONS = ("D",)
_NHL_GOALIE_POSITIONS = ("G",)


def _player_row_tuple(player):
    bad_keys = set(player.keys()) - _PLAYERS_ALLOWED_KEYS
    if bad_keys:
        raise ValueError(f"Invalid player keys: {bad_keys}")
    if player.get("player_id") is None:
        raise ValueError("player_id is required for upsert_player")
    return tuple(player.get(c) for c in _PLAYERS_INSERT_COLUMNS)


def upsert_player(conn, player):
    """Insert or update a row in the players dimension table."""
    cursor = conn.cursor()
    cursor.execute(_PLAYERS_UPSERT_SQL, _player_row_tuple(player))
    conn.commit()


def upsert_players(conn, players):
    """Batch-upsert multiple player dicts via executemany."""
    if not players:
        return
    rows = [_player_row_tuple(p) for p in players]
    cursor = conn.cursor()
    cursor.executemany(_PLAYERS_UPSERT_SQL, rows)
    conn.commit()


def get_missing_player_ids(conn):
    """Return player ids in shot_events that are absent from the players table
    and not already recorded as upstream-unavailable.

    Deduplicates shooter_id and goalie_id, filters NULLs, excludes any
    player_id already present in `players`, and excludes ids recorded in
    `player_metadata_unavailable` so the backfill loop doesn't re-hit the
    API for known-404 ids on every run.
    """
    cursor = conn.cursor()
    cursor.execute(
        """SELECT DISTINCT id FROM (
               SELECT shooter_id AS id FROM shot_events WHERE shooter_id IS NOT NULL
               UNION
               SELECT goalie_id AS id FROM shot_events WHERE goalie_id IS NOT NULL
           )
           WHERE id NOT IN (SELECT player_id FROM players)
             AND id NOT IN (SELECT player_id FROM player_metadata_unavailable)
           ORDER BY id"""
    )
    return [row[0] for row in cursor.fetchall()]


def backfill_player_metadata(conn, fetch_fn, batch_size=50):
    """Fetch and upsert players missing from the players dimension table.

    fetch_fn(player_id) must return a dict with `_PLAYERS_INSERT_COLUMNS`
    keys, or None for a transient failure that should be retried on the
    next run. It may raise `PlayerMetadataNotFound` to signal that the
    upstream source definitively has no record for the id; such ids are
    recorded in `player_metadata_unavailable` and skipped by future runs.

    Writes accumulate in batches of batch_size to amortize the commit cost.
    Returns (attempted, upserted, unavailable) counts.
    """
    missing_ids = get_missing_player_ids(conn)
    total_missing = len(missing_ids)
    print(f"Fetching metadata for {total_missing} players")
    attempted = 0
    upserted = 0
    unavailable = 0
    row_buffer = []
    unavailable_buffer = []

    for player_id in missing_ids:
        attempted += 1
        if attempted % batch_size == 0:
            print(f"  player metadata: [{attempted}/{total_missing}]")
        try:
            row = fetch_fn(player_id)
        except PlayerMetadataNotFound:
            unavailable_buffer.append(player_id)
            unavailable += 1
            if len(unavailable_buffer) >= batch_size:
                mark_players_metadata_unavailable(conn, unavailable_buffer)
                unavailable_buffer = []
            continue
        if row is None:
            continue
        row_buffer.append(row)
        if len(row_buffer) >= batch_size:
            upsert_players(conn, row_buffer)
            upserted += len(row_buffer)
            row_buffer = []

    if row_buffer:
        upsert_players(conn, row_buffer)
        upserted += len(row_buffer)
    if unavailable_buffer:
        mark_players_metadata_unavailable(conn, unavailable_buffer)

    return attempted, upserted, unavailable


def _position_group(position):
    """Map an NHL position code to its F/D/G position group, or None."""
    if position in _NHL_FORWARD_POSITIONS:
        return "F"
    if position in _NHL_DEFENSE_POSITIONS:
        return "D"
    if position in _NHL_GOALIE_POSITIONS:
        return "G"
    return None


def populate_player_game_stats(conn):
    """Derive per-player counting stats from shot_events and upsert into
    player_game_stats.

    Shooters contribute shot and goal counts; goalies get a row for every
    game they appear in (with team_id derived from the games table). TOI,
    assists, and non-shot counters remain at their NOT NULL DEFAULT 0 values
    until richer sources (shifts, boxscore) arrive in later phases.

    Returns the number of rows upserted.
    """
    cursor = conn.cursor()

    cursor.execute(
        """SELECT se.shooter_id, se.game_id, se.shooting_team_id,
                  p.position,
                  COUNT(*) AS shots,
                  SUM(CASE WHEN se.is_goal = 1 THEN 1 ELSE 0 END) AS goals
           FROM shot_events AS se
           LEFT JOIN players AS p ON p.player_id = se.shooter_id
           WHERE se.shooter_id IS NOT NULL
           GROUP BY se.shooter_id, se.game_id, se.shooting_team_id, p.position"""
    )
    shooter_rows = cursor.fetchall()

    cursor.execute(
        """SELECT se.goalie_id, se.game_id,
                  CASE WHEN se.shooting_team_id = g.home_team_id
                       THEN g.away_team_id ELSE g.home_team_id END AS goalie_team_id,
                  p.position
           FROM shot_events AS se
           LEFT JOIN games AS g ON g.game_id = se.game_id
           LEFT JOIN players AS p ON p.player_id = se.goalie_id
           WHERE se.goalie_id IS NOT NULL
           GROUP BY se.goalie_id, se.game_id, goalie_team_id, p.position"""
    )
    goalie_rows = cursor.fetchall()

    batch = []
    for shooter_id, game_id, team_id, position, shots, goals in shooter_rows:
        group = _position_group(position) or "F"
        batch.append((shooter_id, game_id, team_id, group, int(shots), int(goals or 0)))

    for goalie_id, game_id, team_id, position in goalie_rows:
        group = _position_group(position) or "G"
        batch.append((goalie_id, game_id, team_id, group, 0, 0))

    if not batch:
        return 0

    cursor.executemany(
        """INSERT INTO player_game_stats
               (player_id, game_id, team_id, position_group, shots, goals)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(player_id, game_id) DO UPDATE SET
               team_id = excluded.team_id,
               position_group = excluded.position_group,
               shots = excluded.shots,
               goals = excluded.goals""",
        batch,
    )
    conn.commit()
    return len(batch)


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

_GAME_CONTEXT_REST_COLUMNS = (
    "home_rest_days",
    "away_rest_days",
    "rest_advantage",
    "home_is_back_to_back",
    "away_is_back_to_back",
)
_GAME_CONTEXT_TRAVEL_COLUMNS = ("travel_distance_km", "timezone_delta")


def _count_nulls(cursor, table, column, where_sql="", where_params=()):
    quoted = _quote_identifier(column)
    sql = (
        f"SELECT COUNT(*) FROM {_quote_identifier(table)} "
        f"WHERE {quoted} IS NULL"
    )
    if where_sql:
        sql += f" AND {where_sql}"
    cursor.execute(sql, where_params)
    return cursor.fetchone()[0]


def validate_game_context_quality(conn):
    """Count null-rate and orphan-row quality issues for `game_context`.

    Rest-day nulls on the first game of each team's season are structural
    and reported separately as `structural_null_rest_rows`. Travel and
    timezone nulls reflect missing arena coverage and are always reported
    as unexpected.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM game_context")
    total_rows = cursor.fetchone()[0]

    cursor.execute(
        """SELECT COUNT(*) FROM game_context gc
           LEFT JOIN games g ON g.game_id = gc.game_id
           WHERE g.game_id IS NULL"""
    )
    orphan_rows = cursor.fetchone()[0]

    cursor.execute(
        """SELECT COUNT(*) FROM game_context gc
           JOIN games g ON g.game_id = gc.game_id
           WHERE NOT EXISTS (
               SELECT 1 FROM games g2
               WHERE g2.game_id != g.game_id
                 AND g2.game_date < g.game_date
                 AND (g2.home_team_id = g.home_team_id
                      OR g2.away_team_id = g.home_team_id)
           )
              OR NOT EXISTS (
               SELECT 1 FROM games g3
               WHERE g3.game_id != g.game_id
                 AND g3.game_date < g.game_date
                 AND (g3.home_team_id = g.away_team_id
                      OR g3.away_team_id = g.away_team_id)
           )"""
    )
    structural_null_rest_rows = cursor.fetchone()[0]

    result = {
        "total_rows": total_rows,
        "orphan_game_rows": orphan_rows,
        "structural_null_rest_rows": structural_null_rest_rows,
    }
    for column in _GAME_CONTEXT_REST_COLUMNS:
        result[f"null_{column}_rows"] = _count_nulls(
            cursor, "game_context", column
        )
    for column in _GAME_CONTEXT_TRAVEL_COLUMNS:
        result[f"null_{column}_rows"] = _count_nulls(
            cursor, "game_context", column
        )
    return result

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


def create_shifts_table(conn):
    """Create raw shift table used for on-ice reconstruction."""
    cursor = conn.cursor()
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS shifts (
            game_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            period INTEGER NOT NULL,
            start_seconds INTEGER NOT NULL,
            end_seconds INTEGER NOT NULL,
            shift_schema_version TEXT NOT NULL DEFAULT '{_SHIFT_SCHEMA_VERSION}',
            PRIMARY KEY (game_id, player_id, period, start_seconds, end_seconds)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_shifts_game_period "
        "ON shifts(game_id, period)"
    )
    conn.commit()


def create_on_ice_intervals_table(conn):
    """Create normalized on-ice interval table."""
    cursor = conn.cursor()
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS on_ice_intervals (
            game_id INTEGER NOT NULL,
            period INTEGER NOT NULL,
            start_s INTEGER NOT NULL,
            end_s INTEGER NOT NULL,
            home_skaters_json TEXT NOT NULL,
            away_skaters_json TEXT NOT NULL,
            home_goalie_player_id INTEGER,
            away_goalie_player_id INTEGER,
            strength_state TEXT,
            on_ice_schema_version TEXT NOT NULL DEFAULT '{_ON_ICE_SCHEMA_VERSION}',
            PRIMARY KEY (game_id, period, start_s, end_s)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_on_ice_intervals_game_period "
        "ON on_ice_intervals(game_id, period)"
    )
    conn.commit()


def create_player_team_history_table(conn):
    """Create transaction ledger table for team history."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS player_team_history (
            player_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            reason TEXT NOT NULL,
            PRIMARY KEY (player_id, team_id, start_date)
        )
        """
    )
    conn.commit()


def create_player_absences_table(conn):
    """Create absence spells table."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS player_absences (
            player_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            reason TEXT NOT NULL,
            source TEXT,
            PRIMARY KEY (player_id, team_id, start_date, reason)
        )
        """
    )
    conn.commit()


def create_shift_quality_features_table(conn):
    """Create shift-level QoT/QoC features table."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS shift_quality_features (
            game_id INTEGER NOT NULL,
            period INTEGER NOT NULL,
            start_seconds INTEGER NOT NULL,
            end_seconds INTEGER NOT NULL,
            focal_player_id INTEGER NOT NULL,
            qot_off REAL,
            qot_def REAL,
            qoc_off REAL,
            qoc_def REAL,
            PRIMARY KEY (game_id, period, start_seconds, end_seconds, focal_player_id)
        )
        """
    )
    conn.commit()


def create_rapm_player_ratings_table(conn):
    """Create season-level RAPM ratings table."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS rapm_player_ratings (
            season TEXT NOT NULL,
            player_id INTEGER NOT NULL,
            rapm_off REAL,
            rapm_def REAL,
            rapm_off_se REAL,
            rapm_def_se REAL,
            model_version TEXT NOT NULL,
            PRIMARY KEY (season, player_id, model_version)
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
    _migrate_shot_events_v3_to_v4(conn)
    _migrate_games_add_venue_columns(conn)
    create_game_context_table(conn)
    create_venue_bias_diagnostics_table(conn)
    create_shifts_table(conn)
    create_on_ice_intervals_table(conn)
    create_player_team_history_table(conn)
    create_player_absences_table(conn)
    create_shift_quality_features_table(conn)
    create_rapm_player_ratings_table(conn)


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
