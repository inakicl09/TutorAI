"""TutorAI prototype: a Socratic tutor powered by a local Ollama model.
Run this in iTerm with: python3 tutor.py

This is the original command-line prototype, kept for quick testing
without Streamlit. See app.py for the full RAG-enabled version.
"""

import json
import urllib.error
import urllib.request

import chat_storage
import config
import prompts
import subjects
import translations
import users

QUIT_WORDS = {"quit", "exit", "salir"}


def get_available_models() -> list[str]:
    """Ask Ollama which chat models are installed locally.

    The embedding model is left out since it can't hold a conversation.
    Raises urllib.error.URLError if Ollama isn't running.
    """
    with urllib.request.urlopen(config.OLLAMA_TAGS_URL) as response:
        response_body = json.loads(response.read())

    all_model_names = [model["name"] for model in response_body["models"]]
    return [
        model_name
        for model_name in all_model_names
        if not model_name.startswith(config.EMBEDDING_MODEL_NAME)
    ]


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
    """Ask the student to log in or create an account. Returns the
    logged-in username."""
    print(text["cli_login_or_signup"])
    while True:
        choice = input("> ").strip()
        if choice in ("1", "2"):
            break
        print(text["cli_invalid_number"])

    while True:
        username = input(text["cli_username_prompt"]).strip()
        password = input(text["cli_password_prompt"]).strip()

        if choice == "1":
            if users.verify_login(username, password):
                return username
            print(text["cli_login_failed"])
        else:
            if users.username_exists(username):
                print(text["cli_signup_username_taken"])
                continue
            users.create_user(username, password)
            return username


def choose_grade(text: dict) -> str:
    """Ask the student which grade (curso) they are in."""
    chosen_index = choose_from_list(
        text["grade_label"] + ":", subjects.GRADES, text["cli_invalid_number"]
    )
    return subjects.GRADES[chosen_index]


def choose_subject(text: dict, grade: str) -> str:
    """Ask the student which subject to study, from the ones offered at
    their grade."""
    grade_subjects = subjects.GRADE_SUBJECTS[grade]
    chosen_index = choose_from_list(
        text["cli_choose_subject"], grade_subjects, text["cli_invalid_number"]
    )
    return grade_subjects[chosen_index]


def choose_model(available_models: list[str], text: dict) -> str:
    """Ask the student which installed model they want to use."""
    chosen_index = choose_from_list(
        text["cli_choose_model"], available_models, text["cli_invalid_number"]
    )
    return available_models[chosen_index]


def ask_ollama(conversation_history: list[dict], model_name: str) -> str:
    """Send the conversation so far to Ollama and return the tutor's reply."""
    request_body = {
        "model": model_name,
        "messages": conversation_history,
        "stream": False,
    }
    request_data = json.dumps(request_body).encode("utf-8")

    request = urllib.request.Request(
        config.OLLAMA_CHAT_URL,
        data=request_data,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(request) as response:
        response_body = json.loads(response.read())

    return response_body["message"]["content"]


def main() -> None:
    language = choose_language()
    text = translations.TEXT[language]

    print(f"\n{text['cli_title']}")

    username = login_or_signup(text)
    existing_chats = chat_storage.load_chats(username)

    try:
        available_models = get_available_models()
    except urllib.error.URLError:
        print(text["cli_ollama_unreachable"])
        return

    grade = choose_grade(text)
    subject = choose_subject(text, grade)
    selected_model = choose_model(available_models, text)

    print(f"\n{text['cli_instructions']}")

    new_chat = {
        "id": max((c["id"] for c in existing_chats), default=0) + 1,
        "grade": grade,
        "subject": subject,
        "history": [
            {
                "role": "system",
                "content": prompts.build_system_prompt(grade, subject, language),
            }
        ],
    }
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
            tutor_reply = ask_ollama(conversation_history, selected_model)
        except urllib.error.URLError:
            print(text["cli_ollama_disconnected"])
            continue

        conversation_history.append({"role": "assistant", "content": tutor_reply})

        print(f"\n{text['cli_tutor_label']} {tutor_reply}\n")

        chat_storage.save_chats(username, existing_chats + [new_chat])


if __name__ == "__main__":
    main()
