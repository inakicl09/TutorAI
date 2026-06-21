"""One-off script to seed test accounts, so you can see the teacher/admin
dashboards and the student-activity/classes views without signing up 120
accounts by hand.

Run it yourself: python3 -m tutorai.seed_test_data

Creates ~10 teachers and ~120 students (password "test1234" for all of
them), links most students to one or more teachers -- only for the
student's own grade or one grade below, never further -- and gives about
half the students a sample chat with a few backdated messages so "last
active" timestamps actually vary. Safe to re-run: accounts that already
exist are skipped instead of being recreated.

Also fixes any subject_links left over from before that "own grade or
one below" rule existed.
"""

import random
from datetime import datetime, timedelta, timezone

from tutorai import chat_storage, classes, db, prompts, subjects, users

PASSWORD = "test1234"
NUM_TEACHERS = 10
NUM_STUDENTS = 120

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
        num_assignments = random.randint(2, 4)
        for _ in range(num_assignments):
            grade = random.choice(subjects.GRADES)
            subject = random.choice(subjects.GRADE_SUBJECTS[grade])
            users.add_teaching_assignment(username, grade, subject)

    return teacher_usernames


def fix_invalid_subject_links() -> int:
    """Remove any subject_link created before the "own grade or one
    grade below" rule existed. Returns how many were removed."""
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


def seed_students(teacher_usernames: list[str]) -> list[str]:
    student_usernames = []
    for index in range(1, NUM_STUDENTS + 1):
        username = f"alumno_test_{index:03d}"
        student_usernames.append(username)
        if users.username_exists(username):
            continue

        grade = random.choice(subjects.GRADES)
        users.create_student(username, PASSWORD, grade)

        allowed_grades = users.allowed_link_grades(grade)
        candidate_assignments = [
            (teacher_username, assignment)
            for teacher_username in teacher_usernames
            for assignment in users.get_user(teacher_username)["teaching"]
            if assignment["grade"] in allowed_grades
        ]
        if not candidate_assignments:
            continue

        num_links = min(random.randint(1, 3), len(candidate_assignments))
        for teacher_username, assignment in random.sample(candidate_assignments, num_links):
            users.link_student_to_teacher(
                username, teacher_username, assignment["grade"], assignment["subject"]
            )

    return student_usernames


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
            username, link["grade"], link["subject"], system_prompt, created_at=base_time.isoformat()
        )

        num_exchanges = random.randint(1, 3)
        for exchange_index in range(num_exchanges):
            student_line, tutor_line = random.choice(SAMPLE_EXCHANGES)
            message_time = base_time + timedelta(minutes=exchange_index * 2)
            chat_storage.add_message(
                chat["id"], "user", student_line, created_at=message_time.isoformat()
            )
            chat_storage.add_message(
                chat["id"],
                "assistant",
                tutor_line,
                created_at=(message_time + timedelta(seconds=30)).isoformat(),
            )


def main() -> None:
    db.init_db()
    classes.ensure_default_classes()

    teacher_usernames = seed_teachers()
    removed_count = fix_invalid_subject_links()
    student_usernames = seed_students(teacher_usernames)
    seed_chat_activity(student_usernames)

    print(f"Removed {removed_count} subject link(s) that were too far from a student's grade.")
    print(f"Seeded {len(teacher_usernames)} teachers and {len(student_usernames)} students.")
    print(f"All seeded accounts use the password: {PASSWORD}")


if __name__ == "__main__":
    main()
