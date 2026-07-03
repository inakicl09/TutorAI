"""One-off script to seed test accounts, so you can see the teacher/admin
dashboards and the student-activity/classes/homerooms views without
signing up 130 accounts by hand.

Run it yourself: python3 -m tutorai.seed_test_data

Creates 10 teachers (each teaching 5-8 classes) and 120 students (20 per
grade, each connected to 4-6 classes), all sharing the simple test
password below -- only ever linking within the student's own grade or one
grade below, never further -- and gives about half the students a sample
chat with a few backdated messages so "last active" timestamps vary.

Safe to re-run: accounts that already exist are skipped instead of being
recreated, but every test account's password is reset to PASSWORD on every
run, so it stays simple even if it was set under an older version.
"""

import random
from datetime import datetime, timedelta, timezone

from tutorai import chat_storage, classes, db, homerooms, prompts, subjects, users

PASSWORD = "1234"
NUM_TEACHERS = 10
STUDENTS_PER_GRADE = 20  # 20 × 6 grades = 120 students total


SAMPLE_EXCHANGES = [
    ("How do I solve this?", "What have you tried so far?"),
    ("Is this the right formula?", "What does each part of that formula represent?"),
    ("I don't understand the question.", "Which word in the question is unclear to you?"),
    ("Is my answer correct?", "How could you check that yourself?"),
    ("Can you just tell me the answer?", "What's your best guess, and why?"),
]


def seed_teachers() -> list[str]:
    teacher_usernames = []
    for index in range(1, NUM_TEACHERS + 1):
        username = f"profesor_test_{index:02d}"
        teacher_usernames.append(username)
        if users.username_exists(username):
            continue

        users.create_teacher(username, PASSWORD)
        # 5-8 assignments so there are enough classes for students needing 4-6 links.
        num_assignments = random.randint(5, 8)
        for _ in range(num_assignments):
            grade = random.choice(subjects.GRADES)
            subject = random.choice(subjects.GRADE_SUBJECTS[grade])
            users.add_teaching_assignment(username, grade, subject)

    return teacher_usernames


def top_up_teacher_assignments(teacher_usernames: list[str]) -> int:
    """Existing teachers seeded under an older, lower range may have fewer
    than 5 classes. Add more until each has at least 5. Returns how many
    assignments were added."""
    added = 0
    for username in teacher_usernames:
        teaching = users.get_user(username)["teaching"]
        target = random.randint(5, 8)
        attempts = 0
        while len(teaching) < target and attempts < 30:
            attempts += 1
            grade = random.choice(subjects.GRADES)
            subject = random.choice(subjects.GRADE_SUBJECTS[grade])
            if any(a["grade"] == grade and a["subject"] == subject for a in teaching):
                continue
            users.add_teaching_assignment(username, grade, subject)
            teaching.append({"grade": grade, "subject": subject})
            added += 1

    return added


def fix_invalid_subject_links() -> int:
    """Remove any subject_link created before the "own grade or one grade
    below" rule existed. Returns how many were removed."""
    removed = 0
    for user in users.list_all_users():
        if user["role"] != "student":
            continue

        student = users.get_user(user["username"])
        allowed_grades = users.allowed_link_grades(student["grade"])
        for link in student["subject_links"]:
            if link["grade"] not in allowed_grades:
                users.unlink_student_from_teacher(
                    user["username"], link["teacher"], link["grade"], link["subject"]
                )
                removed += 1

    return removed


def _candidate_assignments_for_grade(grade: str, teacher_usernames: list[str]) -> list[tuple]:
    """List (teacher_username, assignment) pairs valid for a student of this
    grade -- i.e. the teacher teaches at the student's own grade or one below."""
    allowed_grades = users.allowed_link_grades(grade)
    return [
        (teacher_username, assignment)
        for teacher_username in teacher_usernames
        for assignment in users.get_user(teacher_username)["teaching"]
        if assignment["grade"] in allowed_grades
    ]


def seed_students(teacher_usernames: list[str]) -> list[str]:
    """Create 20 students per grade (120 total), each linked to 4-6 classes."""
    student_usernames = []
    # Build the full list of (grade, index) pairs so students are distributed
    # evenly: 20 per grade in a fixed order, not randomly.
    grade_sequence = [
        (grade, index)
        for grade in subjects.GRADES
        for index in range(1, STUDENTS_PER_GRADE + 1)
    ]

    for global_index, (grade, grade_index) in enumerate(grade_sequence, start=1):
        username = f"alumno_test_{global_index:03d}"
        student_usernames.append(username)
        if users.username_exists(username):
            continue

        users.create_student(username, PASSWORD, grade)

        candidate_assignments = _candidate_assignments_for_grade(grade, teacher_usernames)
        if not candidate_assignments:
            continue

        num_links = min(random.randint(4, 6), len(candidate_assignments))
        for teacher_username, assignment in random.sample(candidate_assignments, num_links):
            users.link_student_to_teacher(
                username, teacher_username, assignment["grade"], assignment["subject"]
            )

    return student_usernames


def top_up_student_links(student_usernames: list[str], teacher_usernames: list[str]) -> int:
    """Existing students with fewer than 4 links get more added.
    Returns how many links were added."""
    added = 0
    for username in student_usernames:
        student = users.get_user(username)
        candidate_assignments = _candidate_assignments_for_grade(
            student["grade"], teacher_usernames
        )
        existing = {
            (link["teacher"], link["grade"], link["subject"])
            for link in student["subject_links"]
        }
        remaining_candidates = [
            (teacher_username, assignment)
            for teacher_username, assignment in candidate_assignments
            if (teacher_username, assignment["grade"], assignment["subject"]) not in existing
        ]

        target = random.randint(4, 6)
        num_to_add = min(max(target - len(existing), 0), len(remaining_candidates))
        if num_to_add <= 0:
            continue

        for teacher_username, assignment in random.sample(remaining_candidates, num_to_add):
            users.link_student_to_teacher(
                username, teacher_username, assignment["grade"], assignment["subject"]
            )
            added += 1

    return added


def seed_chat_activity(student_usernames: list[str]) -> None:
    for username in student_usernames:
        if random.random() > 0.5:
            continue  # leave about half the students with no activity

        subject_links = users.get_user(username)["subject_links"]
        if not subject_links:
            continue

        link = random.choice(subject_links)
        days_ago = random.randint(0, 30)
        base_time = datetime.now(timezone.utc) - timedelta(days=days_ago)

        system_prompt = prompts.build_system_prompt(link["grade"], link["subject"], "es")
        chat = chat_storage.create_chat(
            username, link["grade"], link["subject"], system_prompt,
            created_at=base_time.isoformat(),
        )

        num_exchanges = random.randint(1, 3)
        for exchange_index in range(num_exchanges):
            student_line, tutor_line = random.choice(SAMPLE_EXCHANGES)
            message_time = base_time + timedelta(minutes=exchange_index * 2)
            chat_storage.add_message(
                chat["id"], "user", student_line, created_at=message_time.isoformat()
            )
            chat_storage.add_message(
                chat["id"], "assistant", tutor_line,
                created_at=(message_time + timedelta(seconds=30)).isoformat(),
            )


def reset_test_passwords(usernames: list[str]) -> None:
    """Force every test account's password back to PASSWORD."""
    for username in usernames:
        users.set_password(username, PASSWORD)


def main() -> None:
    db.init_db()
    classes.sync_with_teaching_assignments()
    homerooms.backfill_homerooms()

    teacher_usernames = seed_teachers()
    topped_up_teaching_count = top_up_teacher_assignments(teacher_usernames)
    removed_count = fix_invalid_subject_links()
    student_usernames = seed_students(teacher_usernames)
    topped_up_links_count = top_up_student_links(student_usernames, teacher_usernames)
    seed_chat_activity(student_usernames)
    reset_test_passwords(teacher_usernames + student_usernames)

    total_students = STUDENTS_PER_GRADE * len(subjects.GRADES)
    print(f"Seeded {len(teacher_usernames)} teachers and {total_students} students "
          f"({STUDENTS_PER_GRADE} per grade).")
    print(f"Added {topped_up_teaching_count} teaching assignment(s) so every teacher has at least 5.")
    print(f"Removed {removed_count} subject link(s) that were too far from a student's grade.")
    print(f"Added {topped_up_links_count} subject link(s) so every student has at least 4 classes.")
    print(f"All seeded accounts use the password: {PASSWORD}")


if __name__ == "__main__":
    main()
