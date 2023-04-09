# database.py

import sqlite3
from sqlite3 import Error


def create_table(conn, table_name):
    cursor = conn.cursor()

    table_name = f"game_{table_name}"  # Add the prefix to the table name

    create_table_query = f"""CREATE TABLE IF NOT EXISTS {table_name} (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                period INTEGER,
                                time TEXT,
                                event TEXT,
                                description TEXT
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

        insert_query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        cursor.execute(insert_query, values)

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