from tutorai import subjects


def test_every_grade_has_at_least_one_subject():
    for grade in subjects.GRADES:
        assert grade in subjects.GRADE_SUBJECTS
        assert len(subjects.GRADE_SUBJECTS[grade]) > 0


def test_grade_subjects_has_no_extra_grades():
    assert set(subjects.GRADE_SUBJECTS.keys()) == set(subjects.GRADES)


def test_subjects_within_a_grade_are_unique():
    for grade, subject_list in subjects.GRADE_SUBJECTS.items():
        assert len(subject_list) == len(set(subject_list)), f"duplicate subject in {grade}"
