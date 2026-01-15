import sqlite3
from contextlib import closing
import server_utils

def create_db(is_test=False):
    db_filename = server_utils.get_db_filename(is_test)

    creator_sql_filename = './sql_scripts/create_db.sql'
    with open(creator_sql_filename, "r") as f:
        creator_sql = f.read()

    with sqlite3.connect(db_filename) as connection:
        with closing(connection.cursor()) as cursor:
            cursor.executescript(creator_sql)
            connection.commit()

def insert_test_data():
    db_filename = server_utils.get_db_filename(is_test=True)
    test_dataset = [
        {"session_id": "4cjlh0q21j", "instrument_id": "5"},
        {"session_id": "fwvum8wqew", "instrument_id": "9"},
        {"session_id": "0skvxy8ahj", "instrument_id": "8"},
        {"session_id": "lzoqnrgyhy", "instrument_id": "11"},
        {"session_id": "duc4p4v33v", "instrument_id": "10"},
        {"session_id": "6wgsvfacxc", "instrument_id": "20"},
        {"session_id": "25z8bp9fo6", "instrument_id": "20"},
        {"session_id": "buypxv2tc5", "instrument_id": "4"},
        {"session_id": "gtjn93ntfv", "instrument_id": "2"}
    ]
    insert_sql = 'INSERT INTO sessions (session_id, instrument_id) VALUES (?, ?)'
    with sqlite3.connect(db_filename) as connection:
        with closing(connection.cursor()) as cursor:
            for test_data in test_dataset:
                cursor.execute(insert_sql, (test_data['session_id'], test_data['instrument_id']))
            connection.commit()


def inspect_db(is_test=False):
    db_filename = server_utils.get_db_filename(is_test)
    with sqlite3.connect(db_filename) as connection:
        with closing(connection.cursor()) as cursor:
            table_display_sql = "SELECT name FROM sqlite_master WHERE type='table';"
            tables = cursor.execute(table_display_sql).fetchall()
            print('Tables:\n')
            print(tables)

            print('')

            data_display_sql = "SELECT * FROM sessions LIMIT 10;"
            data = cursor.execute(data_display_sql).fetchall()
            print('Data:\n')
            print(data)


if __name__ == '__main__':
    ...

    is_test = True

    create_db(is_test=is_test)
    insert_test_data()
    inspect_db(is_test=is_test)

    is_test = False
    create_db(is_test=is_test)
    inspect_db(is_test=is_test)
