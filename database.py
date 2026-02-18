# database.py

import re
import sqlite3
from datetime import date, datetime
from sqlite3 import Error


def _quote_identifier(name):
    """Return a safely double-quoted SQLite identifier.

    Validates that the name contains only word characters (letters, digits,
    underscores) before quoting, preventing SQL injection via identifier names.
    """
    if not re.match(r'^\w+$', name):
        raise ValueError(f"Invalid identifier: {name!r}")
    return f'"{name}"'


def create_table(conn, table_name):
    cursor = conn.cursor()

    quoted = _quote_identifier(f"game_{table_name}")

    create_table_query = f"""CREATE TABLE IF NOT EXISTS {quoted} (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                period INTEGER,
                                time TEXT,
                                event TEXT,
                                description TEXT,
                                UNIQUE(period, time, event, description)
                             );"""

    cursor.execute(create_table_query)
    conn.commit()


def insert_data(conn, table_name, data_list):
    cursor = conn.cursor()

    quoted = _quote_identifier(f"game_{table_name}")

    for data in data_list:
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data.keys()])
        values = tuple(data.values())

        insert_query = f"INSERT OR IGNORE INTO {quoted} ({columns}) VALUES ({placeholders})"
        cursor.execute(insert_query, values)

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
    cursor = conn.cursor()
    table_name = f"game_{game_id}"
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    if cursor.fetchone() is None:
        return False
    cursor.execute(f"SELECT COUNT(*) FROM {_quote_identifier(table_name)}")
    return cursor.fetchone()[0] > 0


def mark_date_collected(conn, date_str, games_found, games_collected):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO collection_log (date, games_found, games_collected, completed_at) "
        "VALUES (?, ?, ?, ?)",
        (date_str, games_found, games_collected, datetime.now().isoformat())
    )
    conn.commit()


def get_last_collected_date(conn):
    cursor = conn.cursor()
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


def deduplicate_existing_tables(conn):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'game_%'"
    )
    game_tables = [row[0] for row in cursor.fetchall()]

    for table_name in game_tables:
        # Check if the UNIQUE constraint already exists by inspecting the table SQL
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        create_sql = cursor.fetchone()[0]
        if "UNIQUE(period, time, event, description)" in create_sql:
            continue

        print(f"Deduplicating and migrating {table_name}...")
        temp_name = f"{table_name}_dedup_tmp"
        quoted = _quote_identifier(table_name)
        quoted_temp = _quote_identifier(temp_name)
        cursor.execute(f"""CREATE TABLE {quoted_temp} (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            period INTEGER,
                            time TEXT,
                            event TEXT,
                            description TEXT,
                            UNIQUE(period, time, event, description)
                         )""")
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
        """
        CREATE TABLE IF NOT EXISTS player_game_features (
            player_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            season TEXT,
            game_number_for_player INTEGER,
            toi_rank_pos_5g REAL,
            toi_rank_pos_10g REAL,
            toi_rolling_mean_5g REAL,
            points_rolling_10g REAL,
            feature_set_version TEXT DEFAULT 'v1',
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

    cursor.execute(
        "SELECT COUNT(*) FROM player_game_stats WHERE position_group NOT IN ('F', 'D', 'G')"
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
