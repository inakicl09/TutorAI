from tutorai import translations


def test_spanish_and_english_have_the_same_keys():
    assert set(translations.TEXT["es"].keys()) == set(translations.TEXT["en"].keys())


def test_how_it_works_guide_names_the_real_buttons():
    """The guide tells testers which buttons to press, so a renamed button
    must be renamed in the guide too (it once fell behind the UI)."""
    import re

    for language, text in translations.TEXT.items():
        guide = re.sub(r"\s+", " ", text["how_it_works_body"])
        for key in (
            "new_chat_button",
            "go_to_chat_button",
            "add_goal_button",
            "hint_button",
            "report_bug_header",
            "feedback_button",
            "chats_header",
        ):
            assert text[key] in guide, f"{language}: guide doesn't mention {text[key]!r}"
        assert text["chat_placeholder"] in guide, f"{language}: chat placeholder missing"
