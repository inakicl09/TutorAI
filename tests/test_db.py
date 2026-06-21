from tutorai import config, db


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
        "homerooms",
        "classes",
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


def test_init_db_migrates_old_homeroom_style_classes_table(tmp_path, monkeypatch):
    """Simulate a database created before "classes" meant a teacher's
    grade+subject group: a `classes` table shaped (id, name, grade), and
    `users.class_id` pointing into it."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "old_schema_test.db"))

    connection = db.get_connection()
    try:
        connection.executescript(
            """
            DROP TABLE IF EXISTS classes;
            CREATE TABLE classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                grade TEXT NOT NULL
            );
            CREATE TABLE users (
                username TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                grade TEXT,
                join_code TEXT UNIQUE,
                class_id INTEGER REFERENCES classes(id)
            );
            """
        )
        old_class_id = connection.execute(
            "INSERT INTO classes (name, grade) VALUES ('1º ESO - A', '1º ESO')"
        ).lastrowid
        connection.execute(
            "INSERT INTO users (username, role, salt, password_hash, class_id) "
            "VALUES ('ana', 'student', 'salt', 'hash', ?)",
            (old_class_id,),
        )
        connection.commit()
    finally:
        connection.close()

    db.init_db()

    connection = db.get_connection()
    try:
        homeroom_row = connection.execute(
            "SELECT name, grade FROM homerooms WHERE id = ?", (old_class_id,)
        ).fetchone()
        assert homeroom_row["name"] == "1º ESO - A"

        user_row = connection.execute(
            "SELECT homeroom_id FROM users WHERE username = 'ana'"
        ).fetchone()
        assert user_row["homeroom_id"] == old_class_id

        class_columns = [row["name"] for row in connection.execute("PRAGMA table_info(classes)")]
        assert "teacher_username" in class_columns
    finally:
        connection.close()
