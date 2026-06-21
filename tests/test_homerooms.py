from tutorai import homerooms, users


def test_create_student_is_placed_in_a_homeroom_for_their_grade():
    users.create_student("ana", "secret123", "3º ESO")

    student = users.get_user("ana")
    assert student["homeroom_id"] is not None
    assert student["homeroom_name"] == "3º ESO - A"


def test_students_in_homeroom_is_alphabetical():
    users.create_student("zoe", "secret123", "1º ESO")
    users.create_student("ana", "secret123", "1º ESO")

    homeroom = homerooms.assign_homeroom("1º ESO")
    assert homerooms.students_in_homeroom(homeroom["id"]) == ["ana", "zoe"]


def test_assign_homeroom_creates_a_new_one_once_the_first_is_full(monkeypatch):
    monkeypatch.setattr(homerooms, "MAX_STUDENTS_PER_HOMEROOM", 2)

    users.create_student("ana", "secret123", "1º ESO")
    users.create_student("bea", "secret123", "1º ESO")
    users.create_student("cris", "secret123", "1º ESO")

    all_homerooms = homerooms.list_homerooms(grade="1º ESO")
    assert [h["name"] for h in all_homerooms] == ["1º ESO - A", "1º ESO - B"]
    assert homerooms.students_in_homeroom(all_homerooms[0]["id"]) == ["ana", "bea"]
    assert homerooms.students_in_homeroom(all_homerooms[1]["id"]) == ["cris"]


def test_list_homerooms_is_ordered_by_grade_then_name():
    homerooms.assign_homeroom("2º ESO")
    homerooms.assign_homeroom("1º ESO")

    assert [h["grade"] for h in homerooms.list_homerooms()] == ["1º ESO", "2º ESO"]


def test_backfill_homerooms_is_safe_to_call_with_nothing_missing():
    users.create_student("ana", "secret123", "1º ESO")

    homerooms.backfill_homerooms()

    assert users.get_user("ana")["homeroom_name"] == "1º ESO - A"
