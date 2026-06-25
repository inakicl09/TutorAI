from tutorai import sessions, users


def test_create_session_and_resolve_username():
    users.create_student("ana", "secret123", "1º ESO")

    token = sessions.create_session("ana")

    assert sessions.get_username_for_token(token) == "ana"


def test_get_username_for_unknown_token_returns_none():
    assert sessions.get_username_for_token("not-a-real-token") is None


def test_delete_session_invalidates_the_token():
    users.create_student("ana", "secret123", "1º ESO")
    token = sessions.create_session("ana")

    sessions.delete_session(token)

    assert sessions.get_username_for_token(token) is None


def test_delete_sessions_for_user_invalidates_every_token():
    users.create_student("ana", "secret123", "1º ESO")
    token_one = sessions.create_session("ana")
    token_two = sessions.create_session("ana")

    sessions.delete_sessions_for_user("ana")

    assert sessions.get_username_for_token(token_one) is None
    assert sessions.get_username_for_token(token_two) is None


def test_each_session_has_a_distinct_token():
    users.create_student("ana", "secret123", "1º ESO")

    token_one = sessions.create_session("ana")
    token_two = sessions.create_session("ana")

    assert token_one != token_two
