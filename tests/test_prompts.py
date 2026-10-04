from tutorai import prompts, subjects


def test_build_system_prompt_combines_all_pieces():
    prompt = prompts.build_system_prompt("1º ESO", "Matemáticas", "es")

    assert "Matemáticas" in prompt
    assert prompts.GRADE_INSTRUCTIONS["1º ESO"] in prompt
    assert prompts.LANGUAGE_INSTRUCTIONS["es"] in prompt
    assert prompts.COMMON_RULES in prompt


def test_socratic_prompt_allows_a_concrete_hint_when_the_student_is_stuck():
    prompt = prompts.build_system_prompt("1º ESO", "Matemáticas", "es")

    # The tutor must still never hand over the answer...
    assert "Never state the final answer" in prompt
    # ...but a stuck student should get the missing piece of information,
    # not another question they already can't answer.
    assert "still stuck" in prompt
    assert "definition" in prompt
    assert "formula" in prompt
    assert "Never refuse to help" in prompt


def test_build_context_prompt_empty_when_no_chunks():
    assert prompts.build_context_prompt([]) == ""


def test_build_context_prompt_joins_chunks():
    context = prompts.build_context_prompt(["chunk one", "chunk two"])

    assert "chunk one" in context
    assert "chunk two" in context


def test_every_curriculum_subject_has_a_prompt_focus():
    for subject_list in subjects.GRADE_SUBJECTS.values():
        for subject in subject_list:
            assert subject in prompts.SUBJECT_FOCUS, f"missing SUBJECT_FOCUS for {subject}"


def test_build_logos_system_prompt_combines_all_pieces():
    prompt = prompts.build_logos_system_prompt("1º ESO", "Matemáticas", "es")

    assert "Logos" in prompt
    assert "Matemáticas" in prompt
    assert prompts.GRADE_INSTRUCTIONS["1º ESO"] in prompt
    assert prompts.LANGUAGE_INSTRUCTIONS["es"] in prompt


def test_logos_prompt_differs_from_socratic_prompt():
    socratic_prompt = prompts.build_system_prompt("1º ESO", "Matemáticas", "es")
    logos_prompt = prompts.build_logos_system_prompt("1º ESO", "Matemáticas", "es")

    assert "Never state the final answer" in socratic_prompt
    assert "Never state the final answer" not in logos_prompt


def test_build_logos_analysis_prompt_includes_the_activity_summary():
    prompt = prompts.build_logos_analysis_prompt(
        "1º ESO", "Matemáticas", "es", "Ana: no entiendo las fracciones"
    )

    assert "Logos" in prompt
    assert "Matemáticas" in prompt
    assert "no entiendo las fracciones" in prompt
    assert prompts.GRADE_INSTRUCTIONS["1º ESO"] in prompt
    assert prompts.LANGUAGE_INSTRUCTIONS["es"] in prompt


def test_build_artemis_system_prompt_is_not_tied_to_grade_or_subject():
    prompt = prompts.build_artemis_system_prompt("es")

    assert "Artemis" in prompt
    assert prompts.LANGUAGE_INSTRUCTIONS["es"] in prompt


def test_build_material_context_prompt_empty_when_no_chunks():
    assert prompts.build_material_context_prompt([]) == ""


def test_build_material_context_prompt_is_worded_for_the_teacher():
    context = prompts.build_material_context_prompt(["chunk one"])

    assert "chunk one" in context
    assert "teacher" in context.lower()
    assert "student's course documents" not in context


def test_build_structured_test_prompt_includes_format_instructions_and_count():
    prompt = prompts.build_structured_test_prompt("3º ESO", "Matemáticas", "es", 5)

    assert "Matemáticas" in prompt
    assert "5" in prompt
    assert "QUESTION:" in prompt
    assert "CORRECT:" in prompt
    assert prompts.QUESTION_SEPARATOR in prompt
    assert prompts.GRADE_INSTRUCTIONS["3º ESO"] in prompt
    assert prompts.LANGUAGE_INSTRUCTIONS["es"] in prompt


def test_build_structured_test_prompt_includes_material_when_given():
    prompt = prompts.build_structured_test_prompt(
        "3º ESO", "Matemáticas", "es", 5, material_context="Reference: fractions chapter"
    )

    assert "Reference: fractions chapter" in prompt
