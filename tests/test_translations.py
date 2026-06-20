from tutorai import translations


def test_spanish_and_english_have_the_same_keys():
    assert set(translations.TEXT["es"].keys()) == set(translations.TEXT["en"].keys())
