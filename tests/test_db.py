from tutorai import db


def test_init_db_creates_expected_tables():
    connection = db.get_connection()
    try:
        table_names = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    finally:
        connection.close()

    expected_tables = {
        "users",
        "teaching_assignments",
        "subject_links",
        "chats",
        "chat_messages",
        "tests",
    }
    assert expected_tables.issubset(table_names)


def test_init_db_is_safe_to_call_twice():
    db.init_db()
    db.init_db()


def test_get_connection_enables_foreign_keys():
    connection = db.get_connection()
    try:
        foreign_keys_on = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        assert foreign_keys_on == 1
    finally:
        connection.close()
