"""TutorAI prototype: a Socratic tutor powered by the Groq API.
Run this in iTerm with: python3 -m tutorai.tutor

This is the original command-line prototype, kept for quick testing
without Streamlit. The rich teacher/admin dashboards (search by
subject+grade, viewing student chats, etc.) only exist in app.py — here,
students can still link to a teacher with a join code and chat, but
teacher/admin accounts are told to use the web app instead.
"""

from tutorai import chat, chat_storage, classes, config, db, homerooms, prompts, subjects, translations, users

QUIT_WORDS = {"quit", "exit", "salir"}


def choose_from_list(prompt_label: str, options: list[str], invalid_message: str) -> int:
    """Print a numbered list and ask the student to pick one. Returns the
    chosen index (0-based)."""
    print(prompt_label)
    for index, option in enumerate(options, start=1):
        print(f"{index}. {option}")

    while True:
        choice = input("> ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return int(choice) - 1
        print(invalid_message)


def choose_language() -> str:
    """Ask the student which UI language they want, before any other text
    can be localized."""
    language_codes = list(translations.TEXT.keys())
    language_names = ["Español" if code == "es" else "English" for code in language_codes]
    chosen_index = choose_from_list(
        "Idioma / Language:", language_names, "Numero no válido / Invalid number."
    )
    return language_codes[chosen_index]


def login_or_signup(text: dict) -> str:
    """Ask the user to log in or create an account. Returns the
    logged-in username."""
    print(text["cli_login_or_signup"])
    while True:
        choice = input("> ").strip()
        if choice in ("1", "2"):
            break
        print(text["cli_invalid_number"])

    if choice == "1":
        while True:
            username = input(text["cli_username_prompt"]).strip()
            password = input(text["cli_password_prompt"]).strip()
            if users.verify_login(username, password):
                return username
            print(text["cli_login_failed"])

    print(text["cli_role_prompt"])
    while True:
        role_choice = input("> ").strip()
        if role_choice in ("1", "2"):
            break
        print(text["cli_invalid_number"])

    while True:
        username = input(text["cli_username_prompt"]).strip()
        password = input(text["cli_password_prompt"]).strip()
        if not users.username_exists(username):
            break
        print(text["cli_signup_username_taken"])

    if role_choice == "1":
        grade = choose_grade(text)
        users.create_student(username, password, grade)
    else:
        join_code = users.create_teacher(username, password)
        print(f"{text['join_code_label']}: {join_code}")

    return username


def choose_grade(text: dict) -> str:
    """Ask the student which grade (curso) they are in."""
    chosen_index = choose_from_list(
        text["grade_label"] + ":", subjects.GRADES, text["cli_invalid_number"]
    )
    return subjects.GRADES[chosen_index]


def link_teacher_by_code(text: dict, username: str) -> None:
    """Ask the student for a teacher's join code and link them to one of
    that teacher's grade+subject combos."""
    while True:
        join_code = input(text["cli_join_code_prompt"]).strip().upper()
        teacher_username = users.find_teacher_by_join_code(join_code)
        if teacher_username is None:
            print(text["cli_join_code_invalid"])
            continue

        teacher_record = users.get_user(teacher_username)
        if not teacher_record["teaching"]:
            print(text["cli_no_teaching_for_link"])
            continue

        teaching_labels = [
            f"{a['subject']} ({a['grade']})" for a in teacher_record["teaching"]
        ]
        chosen_index = choose_from_list(
            text["cli_choose_subject"], teaching_labels, text["cli_invalid_number"]
        )
        assignment = teacher_record["teaching"][chosen_index]
        users.link_student_to_teacher(
            username, teacher_username, assignment["grade"], assignment["subject"]
        )
        print(text["link_success"])
        return


def choose_subject_link(text: dict, username: str) -> dict:
    """Ask the student which of their linked grade+subject combos to chat
    about, linking a teacher first if they have none yet."""
    while True:
        subject_links = users.get_user(username)["subject_links"]
        if subject_links:
            break
        print(text["no_links_message"])
        link_teacher_by_code(text, username)

    link_labels = [f"{link['subject']} ({link['grade']})" for link in subject_links]
    unique_labels = list(dict.fromkeys(link_labels))
    chosen_index = choose_from_list(
        text["cli_choose_subject"], unique_labels, text["cli_invalid_number"]
    )
    return subject_links[link_labels.index(unique_labels[chosen_index])]


def choose_model(available_models: list[str], text: dict) -> str:
    """Ask the student which model they want to use."""
    chosen_index = choose_from_list(
        text["cli_choose_model"], available_models, text["cli_invalid_number"]
    )
    return available_models[chosen_index]


def main() -> None:
    db.init_db()
    classes.sync_with_teaching_assignments()
    homerooms.backfill_homerooms()

    language = choose_language()
    text = translations.TEXT[language]

    print(f"\n{text['cli_title']}")

    username = login_or_signup(text)
    role = users.get_user(username)["role"]

    print(f"\n=== {config.ASSISTANT_NAMES[role]} ===")

    if role != "student":
        print(f"\n{text['cli_teacher_cli_message']}")
        return

    if not chat.is_api_key_configured():
        print(text["cli_ollama_not_installed"])
        return

    available_models = chat.get_available_models()
    chosen_link = choose_subject_link(text, username)
    selected_model = choose_model(available_models, text)

    print(f"\n{text['cli_instructions']}")

    system_prompt = prompts.build_system_prompt(
        chosen_link["grade"], chosen_link["subject"], language
    )
    new_chat = chat_storage.create_chat(
        username, chosen_link["grade"], chosen_link["subject"], system_prompt
    )
    conversation_history = new_chat["history"]

    while True:
        student_message = input(text["cli_you_label"]).strip()

        if student_message.lower() in QUIT_WORDS:
            print(text["cli_goodbye"])
            break

        if student_message == "":
            continue

        conversation_history.append({"role": "user", "content": student_message})

        try:
            tutor_reply = chat._call_groq_chat(conversation_history, selected_model)
        except Exception:
            print(text["cli_ollama_disconnected"])
            # Remove the message we just appended so the history stays consistent.
            conversation_history.pop()
            continue

        conversation_history.append({"role": "assistant", "content": tutor_reply})

        print(f"\n{text['cli_tutor_label']} {tutor_reply}\n")

        chat_storage.add_message(new_chat["id"], "user", student_message)
        chat_storage.add_message(new_chat["id"], "assistant", tutor_reply)


if __name__ == "__main__":
    main()
