"""Server configuration utilities."""

def get_db_filename(is_test):
    """Returns the SQLite database filename for the given environment.

    Args:
        is_test (bool): If True, returns the test DB filename.

    Returns:
        str: Path to the appropriate SQLite database file.
    """
    prod_db_filename = 'octavio_prod.db'
    test_db_filename = 'octavio_test.db'
    db_filename = test_db_filename if is_test else prod_db_filename
    return db_filename
