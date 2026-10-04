from tutorai import chat_storage, seed_test_data, subjects, users


def _all_subjects() -> list[str]:
    all_subjects = set()
    for subject_list in subjects.GRADE_SUBJECTS.values():
        for subject in subject_list:
            all_subjects.add(subject)
    return sorted(all_subjects)


def test_every_subject_has_its_own_sample_questions():
    for subject in _all_subjects():
        exchanges = seed_test_data._exchanges_for_subject(subject)
        assert exchanges is not seed_test_data._FALLBACK_EXCHANGES, (
            f"{subject} has no subject-specific sample questions"
        )
        assert len(exchanges) >= 2, f"{subject} needs at least 2 sample questions"


def test_longest_key_wins_for_overlapping_subject_names():
    # "Educación Física" also contains "Física", and "Historia del Arte"
    # also contains "Historia" -- each must get its own questions.
    assert (
        seed_test_data._exchanges_for_subject("Educación Física")
        is seed_test_data._EXCHANGES_BY_SUBJECT["Educación Física"]
    )
    assert (
        seed_test_data._exchanges_for_subject("Historia del Arte")
        is seed_test_data._EXCHANGES_BY_SUBJECT["Historia del Arte"]
    )
    assert (
        seed_test_data._exchanges_for_subject("Empresa y Diseño de Modelos de Negocio")
        is seed_test_data._EXCHANGES_BY_SUBJECT["Modelos de Negocio"]
    )
    assert (
        seed_test_data._exchanges_for_subject("Segunda Lengua Extranjera")
        is seed_test_data._EXCHANGES_BY_SUBJECT["Segunda Lengua Extranjera"]
    )


def test_seed_chat_activity_gives_one_chat_per_linked_subject():
    users.create_student("ana", "secret123", "3º ESO")
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", "3º ESO", "Matemáticas")
    users.add_teaching_assignment("profesor_lopez", "3º ESO", "Música")
    users.link_student_to_teacher("ana", "profesor_lopez", "3º ESO", "Matemáticas")
    users.link_student_to_teacher("ana", "profesor_lopez", "3º ESO", "Música")

    seed_test_data.seed_chat_activity(["ana"])

    chats = chat_storage.load_chats("ana")
    assert sorted(c["subject"] for c in chats) == ["Matemáticas", "Música"]
    for chat in chats:
        student_questions = [m["content"] for m in chat["history"] if m["role"] == "user"]
        assert len(student_questions) >= 2
        # no repeated question inside one chat
        assert len(student_questions) == len(set(student_questions))


def test_seed_chat_activity_does_not_add_chats_twice():
    users.create_student("ana", "secret123", "3º ESO")
    users.create_teacher("profesor_lopez", "secret123")
    users.add_teaching_assignment("profesor_lopez", "3º ESO", "Matemáticas")
    users.link_student_to_teacher("ana", "profesor_lopez", "3º ESO", "Matemáticas")

    seed_test_data.seed_chat_activity(["ana"])
    seed_test_data.seed_chat_activity(["ana"])

    assert len(chat_storage.load_chats("ana")) == 1


def test_seed_demo_if_empty_does_nothing_when_accounts_exist():
    users.create_student("ana", "secret123", "3º ESO")

    assert seed_test_data.seed_demo_if_empty() is False
    assert [u["username"] for u in users.list_all_users()] == ["ana"]
