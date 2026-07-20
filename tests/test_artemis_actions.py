import pytest

from tutorai import artemis_actions, users

SAMPLE_PROPOSAL = """I'll create that student account for you.

ACTION: create_student
PARAM_username: ana
PARAM_password: secret123
PARAM_grade: 1º ESO
END_ACTION

Let me know if you want anything else.
"""


def test_parse_proposed_action_extracts_name_and_params():
    action = artemis_actions.parse_proposed_action(SAMPLE_PROPOSAL)

    assert action["name"] == "create_student"
    assert action["params"] == {
        "username": "ana",
        "password": "secret123",
        "grade": "1º ESO",
    }


def test_parse_proposed_action_returns_none_for_plain_text():
    assert artemis_actions.parse_proposed_action("Just a normal reply, no action here.") is None


def test_parse_proposed_action_rejects_unknown_ability():
    text = "ACTION: delete_the_whole_database\nPARAM_username: ana\nEND_ACTION"
    assert artemis_actions.parse_proposed_action(text) is None


def test_describe_action_is_a_readable_one_liner():
    action = {"name": "create_student", "params": {"username": "ana", "grade": "1º ESO"}}
    description = artemis_actions.describe_action(action)

    assert "create_student" in description
    assert "username=ana" in description
    assert "grade=1º ESO" in description


def test_execute_action_create_student():
    action = {
        "name": "create_student",
        "params": {"username": "ana", "password": "secret123", "grade": "1º ESO"},
    }

    artemis_actions.execute_action(action, current_admin_username="admin1")

    assert users.verify_login("ana", "secret123")


def test_execute_action_create_teacher_returns_join_code():
    action = {
        "name": "create_teacher",
        "params": {"username": "profesor_lopez", "password": "secret123"},
    }

    extra = artemis_actions.execute_action(action, current_admin_username="admin1")

    assert extra.startswith("join_code=")
    teacher = users.get_user("profesor_lopez")
    assert extra == f"join_code={teacher['join_code']}"


def test_execute_action_delete_user_refuses_to_delete_self():
    users.create_admin("admin1", "secret123")
    action = {"name": "delete_user", "params": {"username": "admin1"}}

    with pytest.raises(ValueError):
        artemis_actions.execute_action(action, current_admin_username="admin1")

    assert users.get_user("admin1") is not None


def test_execute_action_delete_user_works_on_others():
    users.create_admin("admin1", "secret123")
    users.create_student("ana", "secret123", "1º ESO")
    action = {"name": "delete_user", "params": {"username": "ana"}}

    artemis_actions.execute_action(action, current_admin_username="admin1")

    assert users.get_user("ana") is None


def test_execute_action_raises_for_missing_parameter():
    action = {"name": "create_student", "params": {"username": "ana"}}  # missing password/grade

    with pytest.raises(ValueError):
        artemis_actions.execute_action(action, current_admin_username="admin1")


def test_execute_action_raises_for_unknown_action():
    action = {"name": "format_hard_drive", "params": {}}

    with pytest.raises(ValueError):
        artemis_actions.execute_action(action, current_admin_username="admin1")


def test_execute_action_rejects_a_hallucinated_grade():
    action = {
        "name": "create_student",
        # A small local model has been observed writing "1er ESO" instead
        # of the official "1º ESO" -- this must be rejected, not silently
        # create a student with a grade that breaks allowed_link_grades.
        "params": {"username": "ana", "password": "secret123", "grade": "1er ESO"},
    }

    with pytest.raises(ValueError):
        artemis_actions.execute_action(action, current_admin_username="admin1")

    assert users.get_user("ana") is None


def test_execute_action_rejects_a_subject_that_does_not_belong_to_the_grade():
    users.create_teacher("profesor_lopez", "secret123")
    action = {
        "name": "add_teaching_assignment",
        "params": {
            "teacher_username": "profesor_lopez",
            "grade": "1º ESO",
            "subject": "Not A Real Subject",
        },
    }

    with pytest.raises(ValueError):
        artemis_actions.execute_action(action, current_admin_username="admin1")

    teacher = users.get_user("profesor_lopez")
    assert teacher["teaching"] == []


def test_execute_action_link_and_unlink_student_to_teacher():
    users.create_student("ana", "secret123", "1º ESO")
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", "1º ESO", "Matemáticas")

    link_action = {
        "name": "link_student_to_teacher",
        "params": {
            "student_username": "ana",
            "teacher_username": "profesor_lopez",
            "grade": "1º ESO",
            "subject": "Matemáticas",
        },
    }
    artemis_actions.execute_action(link_action, current_admin_username="admin1")
    assert users.students_linked_to_teacher("profesor_lopez") == ["ana"]

    unlink_action = {**link_action, "name": "unlink_student_from_teacher"}
    artemis_actions.execute_action(unlink_action, current_admin_username="admin1")
    assert users.students_linked_to_teacher("profesor_lopez") == []


def test_every_ability_name_is_unique():
    names = [ability["name"] for ability in artemis_actions.ABILITIES]
    assert len(names) == len(set(names))


def test_build_abilities_reference_lists_every_ability():
    reference = artemis_actions.build_abilities_reference()
    for ability in artemis_actions.ABILITIES:
        assert ability["name"] in reference
