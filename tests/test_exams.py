import pytest

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


SAMPLE_STRUCTURED_TEXT = """QUESTION: What is 2+2?
A) 3
B) 4
C) 5
D) 6
CORRECT: B
###
QUESTION: What is the capital of France?
A) Berlin
B) Madrid
C) Paris
D) Rome
CORRECT: C
###
"""

SAMPLE_QUESTIONS = exams.parse_structured_test(SAMPLE_STRUCTURED_TEXT)


def test_parse_structured_test_extracts_every_question():
    assert len(SAMPLE_QUESTIONS) == 2
    assert SAMPLE_QUESTIONS[0]["question_text"] == "What is 2+2?"
    assert SAMPLE_QUESTIONS[0]["correct_option"] == "B"
    assert SAMPLE_QUESTIONS[1]["correct_option"] == "C"


def test_parse_structured_test_returns_empty_list_for_garbage():
    assert exams.parse_structured_test("this is not a test at all") == []


def _link_student_and_teacher(grade="3º ESO", subject="Matemáticas"):
    users.create_student("ana", "secret123", grade)
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", grade, subject)
    users.link_student_to_teacher("ana", "profesor_lopez", grade, subject)


def test_publish_test_creates_questions_and_is_visible_to_linked_students():
    _link_student_and_teacher()

    test_id = exams.publish_test(
        "profesor_lopez", "3º ESO", "Matemáticas", "Examen 1", SAMPLE_QUESTIONS
    )

    questions = exams.get_test_questions(test_id)
    assert len(questions) == 2

    available = exams.list_published_tests_for_student("ana")
    assert [t["id"] for t in available] == [test_id]


def test_unpublished_freeform_test_is_not_visible_to_students():
    _link_student_and_teacher()
    exams.save_test("profesor_lopez", "3º ESO", "Matemáticas", "Draft only", "some text")

    assert exams.list_published_tests_for_student("ana") == []


def test_submit_test_grades_correctly_and_records_one_attempt():
    _link_student_and_teacher()
    test_id = exams.publish_test(
        "profesor_lopez", "3º ESO", "Matemáticas", "Examen 1", SAMPLE_QUESTIONS
    )
    questions = exams.get_test_questions(test_id)

    answers = {questions[0]["id"]: "B", questions[1]["id"]: "A"}  # one right, one wrong
    result = exams.submit_test(test_id, "ana", answers)

    assert result == {"score": 1, "total": 2}
    assert exams.get_submission(test_id, "ana") is not None

    submissions = exams.list_submissions(test_id)
    assert len(submissions) == 1
    assert submissions[0]["student_username"] == "ana"


def test_submit_test_rejects_a_second_attempt():
    _link_student_and_teacher()
    test_id = exams.publish_test(
        "profesor_lopez", "3º ESO", "Matemáticas", "Examen 1", SAMPLE_QUESTIONS
    )
    questions = exams.get_test_questions(test_id)
    answers = {q["id"]: q["correct_option"] for q in questions}

    exams.submit_test(test_id, "ana", answers)

    with pytest.raises(ValueError):
        exams.submit_test(test_id, "ana", answers)


def test_delete_test_removes_questions_and_submissions():
    _link_student_and_teacher()
    test_id = exams.publish_test(
        "profesor_lopez", "3º ESO", "Matemáticas", "Examen 1", SAMPLE_QUESTIONS
    )
    questions = exams.get_test_questions(test_id)
    exams.submit_test(test_id, "ana", {q["id"]: q["correct_option"] for q in questions})

    exams.delete_test(test_id, "profesor_lopez")

    assert exams.get_test_questions(test_id) == []
    assert exams.list_published_tests_for_student("ana") == []
