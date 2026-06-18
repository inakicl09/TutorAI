"""TutorAI prototype: a Socratic tutor powered by a local Ollama model.
Run this in iTerm with: python3 tutorprototype.py

This is the original command-line prototype, kept for quick testing
without Streamlit. See app.py for the full RAG-enabled version.
"""

import json
import urllib.error
import urllib.request

import config
import prompts


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


def choose_model(available_models: list[str]) -> str:
    """Ask the student which installed model they want to use."""
    print("Modelos disponibles:")
    for index, model_name in enumerate(available_models, start=1):
        print(f"{index}. {model_name}")

    while True:
        choice = input("Elige un modelo (numero): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(available_models):
            return available_models[int(choice) - 1]
        print("Numero no válido, intentalo de nuevo.")


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
    print("=== TutorAI: Socratic Tutor ===")

    try:
        available_models = get_available_models()
    except urllib.error.URLError:
        print("No se pudo conectar con Ollama. Ejecuta 'ollama serve' y vuelve a intentarlo.")
        return

    selected_model = choose_model(available_models)

    print("\nType a question about any school subject.")
    print("Type 'quit' to exit.\n")

    conversation_history = [{"role": "system", "content": prompts.SYSTEM_PROMPT}]

    while True:
        student_message = input("You: ").strip()

        if student_message.lower() in ("quit", "exit"):
            print("Tutor: Goodbye! Keep questioning everything.")
            break

        if student_message == "":
            continue

        conversation_history.append({"role": "user", "content": student_message})

        try:
            tutor_reply = ask_ollama(conversation_history, selected_model)
        except urllib.error.URLError:
            print("Tutor: I can't reach Ollama. Is it running? Try 'ollama serve'.")
            continue

        conversation_history.append({"role": "assistant", "content": tutor_reply})

        print(f"\nTutor: {tutor_reply}\n")


if __name__ == "__main__":
    main()
