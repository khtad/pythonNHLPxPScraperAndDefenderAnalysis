# database.py

import sqlite3
from datetime import date, datetime
from sqlite3 import Error


def create_table(conn, table_name):
    cursor = conn.cursor()

    table_name = f"game_{table_name}"  # Add the prefix to the table name

    create_table_query = f"""CREATE TABLE IF NOT EXISTS {table_name} (
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

    table_name = f"game_{table_name}"  # Add the prefix to the table name

    for data in data_list:
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data.keys()])
        values = tuple(data.values())

        insert_query = f"INSERT OR IGNORE INTO {table_name} ({columns}) VALUES ({placeholders})"
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
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
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
        cursor.execute(f"""CREATE TABLE {temp_name} (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            period INTEGER,
                            time TEXT,
                            event TEXT,
                            description TEXT,
                            UNIQUE(period, time, event, description)
                         )""")
        cursor.execute(
            f"INSERT OR IGNORE INTO {temp_name} (period, time, event, description) "
            f"SELECT period, time, event, description FROM {table_name}"
        )
        cursor.execute(f"DROP TABLE {table_name}")
        cursor.execute(f"ALTER TABLE {temp_name} RENAME TO {table_name}")

    conn.commit()


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