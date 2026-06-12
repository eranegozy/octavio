"""SQLite query functions for session and instrument data.

Provides upsert and read operations against the octavio SQLite database.
Does not store MIDI data — only session metadata used by the frontend API.
"""

import sqlite3
from contextlib import closing
import server_utils

# def add_db_session(session_id, instrument_id, is_test=False):
#     db_filename = server_utils.get_db_filename(is_test)
#     insert_sql = 'INSERT INTO sessions (session_id, instrument_id) VALUES (?, ?)'
#     with sqlite3.connect(db_filename) as connection:
#         with closing(connection.cursor()) as cursor:
#             cursor.execute(insert_sql, (session_id, instrument_id))
#             connection.commit()

# def refresh_db_session(session_id, instrument_id, is_test=False):
#     db_filename = server_utils.get_db_filename(is_test)
#     update_sql = """UPDATE sessions
#                     SET last_updated = datetime('now')
#                     WHERE session_id = ? AND instrument_id = ?;
#                  """
#     with sqlite3.connect(db_filename) as connection:
#         with closing(connection.cursor()) as cursor:
#             cursor.execute(update_sql, (session_id, instrument_id))
#             connection.commit()

def add_or_refresh_db_session(session_id, instrument_id, is_test=False):
    """Inserts a new session record or updates last_updated if it already exists.

    Args:
        session_id (str): The session identifier.
        instrument_id (str): The instrument identifier.
        is_test (bool): If True, targets the test database. Defaults to False.
    """
    db_filename = server_utils.get_db_filename(is_test)
    update_sql = """INSERT INTO sessions (session_id, instrument_id)
                    VALUES (?, ?)
                    ON CONFLICT(session_id, instrument_id)
                    DO UPDATE SET last_updated = datetime('now');
                 """
    with sqlite3.connect(db_filename) as connection:
        with closing(connection.cursor()) as cursor:
            cursor.execute(update_sql, (session_id, instrument_id))
            connection.commit()

def get_db_instruments(is_test=False):
    """Returns all rows from the instruments table.

    Args:
        is_test (bool): If True, queries the test database. Defaults to False.

    Returns:
        list[dict]: All instrument records.
    """
    db_filename = server_utils.get_db_filename(is_test)
    get_instrument_sql = "SELECT * FROM instruments;"
    with sqlite3.connect(db_filename) as connection:
        connection.row_factory = sqlite3.Row  # This is the magic
        with closing(connection.cursor()) as cursor:
            cursor.execute(get_instrument_sql)
            rows = cursor.fetchall()
    data = [dict(row) for row in rows]
    return data

def get_instrument_sessions(instrument_id, is_test=False):
    """Returns the 5 most recent sessions for an instrument lasting at least 2 minutes.

    Args:
        instrument_id (str): The instrument to query.
        is_test (bool): If True, queries the test database. Defaults to False.

    Returns:
        list[dict]: Session records ordered by last_updated descending, with duration_in_seconds.
    """
    db_filename = server_utils.get_db_filename(is_test)
    get_sessions_sql = """
        SELECT
        *,
        (julianday(last_updated) - julianday(created_at)) * 86400 AS duration_in_seconds
        FROM sessions
        WHERE instrument_id = ? AND duration_in_seconds >= 120
        ORDER BY last_updated DESC
        LIMIT 5;
    """
    with sqlite3.connect(db_filename) as connection:
        connection.row_factory = sqlite3.Row  # This is the magic
        with closing(connection.cursor()) as cursor:
            cursor.execute(get_sessions_sql, (instrument_id,))
            rows = cursor.fetchall()
    data = [dict(row) for row in rows]
    return data
