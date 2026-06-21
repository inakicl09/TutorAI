from tutorai import classes, subjects, users


def test_ensure_default_classes_creates_one_per_grade():
    classes.ensure_default_classes()

    all_classes = classes.list_classes()
    assert [c["grade"] for c in all_classes] == subjects.GRADES


def test_ensure_default_classes_is_safe_to_call_twice():
    classes.ensure_default_classes()
    classes.ensure_default_classes()

    assert len(classes.list_classes()) == len(subjects.GRADES)


def test_get_class_for_grade_returns_matching_class():
    classes.ensure_default_classes()

    class_record = classes.get_class_for_grade("3º ESO")

    assert class_record["grade"] == "3º ESO"
    assert class_record["name"] == "3º ESO - A"


def test_create_student_is_placed_in_their_grade_class():
    classes.ensure_default_classes()
    users.create_student("ana", "secret123", "3º ESO")

    expected_class = classes.get_class_for_grade("3º ESO")
    assert users.get_user("ana")["class_id"] == expected_class["id"]
    assert users.get_user("ana")["class_name"] == "3º ESO - A"
    assert classes.students_in_class(expected_class["id"]) == ["ana"]


def test_students_in_class_is_alphabetical():
    classes.ensure_default_classes()
    users.create_student("zoe", "secret123", "1º ESO")
    users.create_student("ana", "secret123", "1º ESO")

    class_record = classes.get_class_for_grade("1º ESO")
    assert classes.students_in_class(class_record["id"]) == ["ana", "zoe"]
