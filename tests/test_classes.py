from tutorai import classes, users


def test_get_or_create_class_creates_a_named_class():
    users.create_teacher("profesor_lopez", "secret123")

    class_record = classes.get_or_create_class("profesor_lopez", "3º ESO", "Matemáticas")

    assert class_record["teacher_username"] == "profesor_lopez"
    assert class_record["grade"] == "3º ESO"
    assert class_record["subject"] == "Matemáticas"
    assert "profesor_lopez" in class_record["name"]


def test_get_or_create_class_is_idempotent():
    users.create_teacher("profesor_lopez", "secret123")

    first = classes.get_or_create_class("profesor_lopez", "3º ESO", "Matemáticas")
    second = classes.get_or_create_class("profesor_lopez", "3º ESO", "Matemáticas")

    assert first["id"] == second["id"]


def test_add_teaching_assignment_creates_a_matching_class():
    users.create_teacher("profesor_lopez", "secret123")

    users.add_teaching_assignment("profesor_lopez", "3º ESO", "Matemáticas")

    matching = classes.list_classes(grade="3º ESO")
    assert len(matching) == 1
    assert matching[0]["teacher_username"] == "profesor_lopez"
    assert matching[0]["subject"] == "Matemáticas"


def test_sync_with_teaching_assignments_backfills_missing_classes():
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", "3º ESO", "Matemáticas")

    classes.sync_with_teaching_assignments()
    classes.sync_with_teaching_assignments()  # safe to call twice

    assert len(classes.list_classes()) == 1


def test_list_classes_filters_by_grade_and_search_text():
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", "3º ESO", "Matemáticas")
    users.add_teaching_assignment("profesor_lopez", "1º ESO", "Música")

    assert len(classes.list_classes(grade="3º ESO")) == 1
    assert len(classes.list_classes(search_text="lopez")) == 2
    assert len(classes.list_classes(search_text="nobody")) == 0


def test_students_in_class_reflects_subject_links():
    users.create_student("ana", "secret123", "3º ESO")
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", "3º ESO", "Matemáticas")
    users.link_student_to_teacher("ana", "profesor_lopez", "3º ESO", "Matemáticas")

    class_record = classes.get_or_create_class("profesor_lopez", "3º ESO", "Matemáticas")
    assert classes.students_in_class(class_record["id"]) == ["ana"]


def test_classes_for_student_lists_every_linked_class():
    users.create_student("ana", "secret123", "3º ESO")
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", "3º ESO", "Matemáticas")
    users.add_teaching_assignment("profesor_lopez", "3º ESO", "Física y Química")
    users.link_student_to_teacher("ana", "profesor_lopez", "3º ESO", "Matemáticas")
    users.link_student_to_teacher("ana", "profesor_lopez", "3º ESO", "Física y Química")

    student_classes = classes.classes_for_student("ana")
    assert {c["subject"] for c in student_classes} == {"Matemáticas", "Física y Química"}
