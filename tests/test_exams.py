from tutorai import exams, users


def test_save_test_and_list_for_teacher():
    users.create_teacher("profesor_lopez", "secret123")

    test_id = exams.save_test(
        "profesor_lopez", "3º ESO", "Matemáticas", "Examen de fracciones", "1. ..."
    )

    saved = exams.list_tests_for_teacher("profesor_lopez")
    assert len(saved) == 1
    assert saved[0]["id"] == test_id
    assert saved[0]["title"] == "Examen de fracciones"
    assert saved[0]["content"] == "1. ..."


def test_list_tests_for_teacher_is_newest_first():
    users.create_teacher("profesor_lopez", "secret123")
    exams.save_test("profesor_lopez", "3º ESO", "Matemáticas", "First", "...")
    exams.save_test("profesor_lopez", "3º ESO", "Matemáticas", "Second", "...")

    titles = [t["title"] for t in exams.list_tests_for_teacher("profesor_lopez")]
    assert titles == ["Second", "First"]


def test_delete_test_only_removes_the_owning_teachers_test():
    users.create_teacher("profesor_lopez", "secret123")
    users.create_teacher("profesora_garcia", "secret123")
    test_id = exams.save_test("profesor_lopez", "3º ESO", "Matemáticas", "Title", "...")

    exams.delete_test(test_id, "profesora_garcia")
    assert len(exams.list_tests_for_teacher("profesor_lopez")) == 1

    exams.delete_test(test_id, "profesor_lopez")
    assert exams.list_tests_for_teacher("profesor_lopez") == []
