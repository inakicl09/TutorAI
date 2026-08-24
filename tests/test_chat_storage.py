from tutorai import chat_storage, db, users


def test_create_chat_includes_system_message():
    users.create_student("ana", "secret123", "1º ESO")

    chat = chat_storage.create_chat("ana", "1º ESO", "Matemáticas", "system prompt text")

    assert chat["grade"] == "1º ESO"
    assert chat["subject"] == "Matemáticas"
    assert chat["history"] == [
        {"role": "system", "content": "system prompt text", "created_at": chat["history"][0]["created_at"]}
    ]


def test_add_message_appends_in_order():
    users.create_student("ana", "secret123", "1º ESO")
    chat = chat_storage.create_chat("ana", "1º ESO", "Matemáticas", "system prompt text")

    chat_storage.add_message(chat["id"], "user", "How do I solve this?")
    chat_storage.add_message(chat["id"], "assistant", "What have you tried so far?")

    [loaded_chat] = chat_storage.load_chats("ana")
    roles = [message["role"] for message in loaded_chat["history"]]
    contents = [message["content"] for message in loaded_chat["history"]]
    assert roles == ["system", "user", "assistant"]
    assert contents == ["system prompt text", "How do I solve this?", "What have you tried so far?"]


def test_load_chats_returns_each_students_own_chats_only():
    users.create_student("ana", "secret123", "1º ESO")
    users.create_student("luis", "secret123", "1º ESO")
    chat_storage.create_chat("ana", "1º ESO", "Matemáticas", "system prompt text")
    chat_storage.create_chat("luis", "1º ESO", "Matemáticas", "system prompt text")

    ana_chats = chat_storage.load_chats("ana")
    assert len(ana_chats) == 1


def test_delete_chat_removes_chat_and_its_messages():
    users.create_student("ana", "secret123", "1º ESO")
    kept_chat = chat_storage.create_chat("ana", "1º ESO", "Matemáticas", "system prompt text")
    doomed_chat = chat_storage.create_chat("ana", "1º ESO", "Biología y Geología", "another prompt")
    chat_storage.add_message(doomed_chat["id"], "user", "Hello?")

    assert chat_storage.delete_chat(doomed_chat["id"], "ana") is True

    remaining_chats = chat_storage.load_chats("ana")
    assert [c["id"] for c in remaining_chats] == [kept_chat["id"]]

    connection = db.get_connection()
    try:
        leftover_messages = connection.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE chat_id = ?", (doomed_chat["id"],)
        ).fetchone()[0]
    finally:
        connection.close()
    assert leftover_messages == 0


def test_delete_chat_refuses_someone_elses_chat():
    users.create_student("ana", "secret123", "1º ESO")
    users.create_student("luis", "secret123", "1º ESO")
    ana_chat = chat_storage.create_chat("ana", "1º ESO", "Matemáticas", "system prompt text")

    assert chat_storage.delete_chat(ana_chat["id"], "luis") is False
    assert len(chat_storage.load_chats("ana")) == 1


def test_delete_chat_returns_false_for_unknown_chat():
    users.create_student("ana", "secret123", "1º ESO")

    assert chat_storage.delete_chat(999, "ana") is False


def test_create_chat_defaults_mode_to_none():
    users.create_student("ana", "secret123", "1º ESO")
    chat = chat_storage.create_chat("ana", "1º ESO", "Matemáticas", "system prompt text")

    assert chat["mode"] is None
    [loaded_chat] = chat_storage.load_chats("ana")
    assert loaded_chat["mode"] is None


def test_create_chat_persists_mode():
    users.create_teacher("profesor_lopez", "secret123")
    chat = chat_storage.create_chat(
        "profesor_lopez", "3º ESO", "Matemáticas", "system prompt text", mode="analyze"
    )

    assert chat["mode"] == "analyze"
    [loaded_chat] = chat_storage.load_chats("profesor_lopez")
    assert loaded_chat["mode"] == "analyze"
