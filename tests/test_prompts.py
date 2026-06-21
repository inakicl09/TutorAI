from tutorai import prompts, subjects


def test_build_system_prompt_combines_all_pieces():
    prompt = prompts.build_system_prompt("1º ESO", "Matemáticas", "es")

    assert "Matemáticas" in prompt
    assert prompts.GRADE_INSTRUCTIONS["1º ESO"] in prompt
    assert prompts.LANGUAGE_INSTRUCTIONS["es"] in prompt
    assert prompts.COMMON_RULES in prompt


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
