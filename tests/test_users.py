import pytest

from tutorai import chat_storage, users


def test_create_and_verify_student_login():
    users.create_student("ana", "secret123", "1º ESO")

    assert users.username_exists("ana")
    assert users.verify_login("ana", "secret123")
    assert not users.verify_login("ana", "wrong-password")


def test_create_student_rejects_duplicate_username():
    users.create_student("ana", "secret123", "1º ESO")

    with pytest.raises(ValueError):
        users.create_student("ana", "another-password", "2º ESO")


def test_get_user_returns_none_for_unknown_username():
    assert users.get_user("nobody") is None


def test_create_teacher_returns_a_join_code():
    join_code = users.create_teacher("profesor_lopez", "secret123")

    assert len(join_code) == users.JOIN_CODE_LENGTH
    assert users.find_teacher_by_join_code(join_code) == "profesor_lopez"


def test_create_admin():
    users.create_admin("admin1", "secret123")

    admin_user = users.get_user("admin1")
    assert admin_user["role"] == "admin"


def test_add_teaching_assignment_and_get_user():
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", "1º ESO", "Matemáticas")

    teacher = users.get_user("profesor_lopez")
    assert {"grade": "1º ESO", "subject": "Matemáticas"} in teacher["teaching"]


def test_find_teachers_filters_by_search_text():
    users.create_teacher("profesor_lopez", "secret123")
    users.create_teacher("profesora_garcia", "secret123")

    assert users.find_teachers("lopez") == ["profesor_lopez"]
    assert set(users.find_teachers("")) == {"profesor_lopez", "profesora_garcia"}


def test_find_teacher_by_join_code_unknown_code_returns_none():
    assert users.find_teacher_by_join_code("ZZZZZZ") is None


def test_link_student_to_teacher_requires_matching_teaching_assignment():
    users.create_student("ana", "secret123", "1º ESO")
    users.create_teacher("profesor_lopez", "secret123")

    with pytest.raises(ValueError):
        users.link_student_to_teacher("ana", "profesor_lopez", "1º ESO", "Matemáticas")


def test_link_student_to_teacher_succeeds_when_teacher_teaches_it():
    users.create_student("ana", "secret123", "1º ESO")
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", "1º ESO", "Matemáticas")

    users.link_student_to_teacher("ana", "profesor_lopez", "1º ESO", "Matemáticas")

    student = users.get_user("ana")
    assert {
        "grade": "1º ESO",
        "subject": "Matemáticas",
        "teacher": "profesor_lopez",
    } in student["subject_links"]
    assert users.students_linked_to_teacher("profesor_lopez") == ["ana"]


def test_allowed_link_grades_includes_own_grade_and_one_below():
    assert users.allowed_link_grades("3º ESO") == {"3º ESO", "2º ESO"}


def test_allowed_link_grades_has_no_grade_below_for_the_first_grade():
    assert users.allowed_link_grades("1º ESO") == {"1º ESO"}


def test_link_student_to_teacher_rejects_grade_above_the_students_own():
    users.create_student("ana", "secret123", "1º ESO")
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", "2º ESO", "Matemáticas")

    with pytest.raises(ValueError):
        users.link_student_to_teacher("ana", "profesor_lopez", "2º ESO", "Matemáticas")


def test_link_student_to_teacher_rejects_grade_more_than_one_below():
    users.create_student("ana", "secret123", "3º ESO")
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", "1º ESO", "Matemáticas")

    with pytest.raises(ValueError):
        users.link_student_to_teacher("ana", "profesor_lopez", "1º ESO", "Matemáticas")


def test_link_student_to_teacher_allows_exactly_one_grade_below():
    users.create_student("ana", "secret123", "3º ESO")
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", "2º ESO", "Matemáticas")

    users.link_student_to_teacher("ana", "profesor_lopez", "2º ESO", "Matemáticas")

    student = users.get_user("ana")
    assert {
        "grade": "2º ESO",
        "subject": "Matemáticas",
        "teacher": "profesor_lopez",
    } in student["subject_links"]


def test_unlink_student_from_teacher_removes_only_that_link():
    users.create_student("ana", "secret123", "2º ESO")
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", "1º ESO", "Matemáticas")
    users.add_teaching_assignment("profesor_lopez", "2º ESO", "Matemáticas")
    users.link_student_to_teacher("ana", "profesor_lopez", "1º ESO", "Matemáticas")
    users.link_student_to_teacher("ana", "profesor_lopez", "2º ESO", "Matemáticas")

    users.unlink_student_from_teacher("ana", "profesor_lopez", "1º ESO", "Matemáticas")

    student = users.get_user("ana")
    assert student["subject_links"] == [
        {"grade": "2º ESO", "subject": "Matemáticas", "teacher": "profesor_lopez"}
    ]


def test_move_student_link_links_new_and_unlinks_old():
    users.create_student("ana", "secret123", "3º ESO")
    users.create_teacher("profesor_lopez", "secret123")
    users.create_teacher("profesora_garcia", "secret123")
    users.add_teaching_assignment("profesor_lopez", "3º ESO", "Matemáticas")
    users.add_teaching_assignment("profesora_garcia", "3º ESO", "Matemáticas")
    users.link_student_to_teacher("ana", "profesor_lopez", "3º ESO", "Matemáticas")

    users.move_student_link(
        "ana", "profesor_lopez", "3º ESO", "Matemáticas", "profesora_garcia", "3º ESO", "Matemáticas"
    )

    student = users.get_user("ana")
    assert student["subject_links"] == [
        {"grade": "3º ESO", "subject": "Matemáticas", "teacher": "profesora_garcia"}
    ]


def test_move_student_link_keeps_old_link_when_new_target_is_invalid():
    users.create_student("ana", "secret123", "3º ESO")
    users.create_teacher("profesor_lopez", "secret123")
    users.create_teacher("profesora_garcia", "secret123")
    users.add_teaching_assignment("profesor_lopez", "3º ESO", "Matemáticas")
    users.link_student_to_teacher("ana", "profesor_lopez", "3º ESO", "Matemáticas")

    with pytest.raises(ValueError):
        # profesora_garcia doesn't teach this grade+subject
        users.move_student_link(
            "ana", "profesor_lopez", "3º ESO", "Matemáticas", "profesora_garcia", "3º ESO", "Matemáticas"
        )

    student = users.get_user("ana")
    assert student["subject_links"] == [
        {"grade": "3º ESO", "subject": "Matemáticas", "teacher": "profesor_lopez"}
    ]


def test_list_all_users_excludes_password_data():
    users.create_student("ana", "secret123", "1º ESO")

    all_users = users.list_all_users()
    assert len(all_users) == 1
    assert "password_hash" not in all_users[0]
    assert "salt" not in all_users[0]


def test_list_all_users_is_alphabetical_and_filters_by_search_text():
    users.create_student("zoe", "secret123", "1º ESO")
    users.create_teacher("ana_profe", "secret123")
    users.create_admin("mid_admin", "secret123")

    assert [u["username"] for u in users.list_all_users()] == [
        "ana_profe",
        "mid_admin",
        "zoe",
    ]
    assert [u["username"] for u in users.list_all_users("an")] == ["ana_profe"]


def test_set_password_changes_login():
    users.create_student("ana", "secret123", "1º ESO")

    users.set_password("ana", "newpassword")

    assert not users.verify_login("ana", "secret123")
    assert users.verify_login("ana", "newpassword")


def test_set_password_rejects_unknown_username():
    with pytest.raises(ValueError):
        users.set_password("nobody", "newpassword")


def test_get_plaintext_password_for_newly_created_student():
    users.create_student("ana", "secret123", "1º ESO")

    assert users.get_plaintext_password("ana") == "secret123"


def test_get_plaintext_password_for_newly_created_teacher():
    users.create_teacher("profesor_lopez", "secret123")

    assert users.get_plaintext_password("profesor_lopez") == "secret123"


def test_get_plaintext_password_reflects_set_password():
    users.create_student("ana", "secret123", "1º ESO")

    users.set_password("ana", "newpassword")

    assert users.get_plaintext_password("ana") == "newpassword"


def test_get_plaintext_password_returns_none_for_unknown_username():
    assert users.get_plaintext_password("nobody") is None


def test_regenerate_join_code_changes_the_code_and_old_one_stops_working():
    old_code = users.create_teacher("profesor_lopez", "secret123")

    new_code = users.regenerate_join_code("profesor_lopez")

    assert new_code != old_code
    assert users.find_teacher_by_join_code(old_code) is None
    assert users.find_teacher_by_join_code(new_code) == "profesor_lopez"


def test_regenerate_join_code_rejects_non_teacher():
    users.create_student("ana", "secret123", "1º ESO")

    with pytest.raises(ValueError):
        users.regenerate_join_code("ana")


def test_delete_user_removes_student_and_their_data():
    users.create_student("ana", "secret123", "1º ESO")
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", "1º ESO", "Matemáticas")
    users.link_student_to_teacher("ana", "profesor_lopez", "1º ESO", "Matemáticas")
    chat = chat_storage.create_chat("ana", "1º ESO", "Matemáticas", "system prompt text")
    chat_storage.add_message(chat["id"], "user", "How do I solve this?")

    users.delete_user("ana")

    assert users.get_user("ana") is None
    assert users.students_linked_to_teacher("profesor_lopez") == []
    assert chat_storage.load_chats("ana") == []


def test_delete_user_removes_teacher_and_their_assignments():
    users.create_student("ana", "secret123", "1º ESO")
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", "1º ESO", "Matemáticas")
    users.link_student_to_teacher("ana", "profesor_lopez", "1º ESO", "Matemáticas")

    users.delete_user("profesor_lopez")

    assert users.get_user("profesor_lopez") is None
    student = users.get_user("ana")
    assert student["subject_links"] == []


def test_delete_user_rejects_unknown_username():
    with pytest.raises(ValueError):
        users.delete_user("nobody")
