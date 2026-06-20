import pytest

from tutorai import users


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


def test_list_all_users_excludes_password_data():
    users.create_student("ana", "secret123", "1º ESO")

    all_users = users.list_all_users()
    assert len(all_users) == 1
    assert "password_hash" not in all_users[0]
    assert "salt" not in all_users[0]
