from tutorai import chat_storage, users


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
