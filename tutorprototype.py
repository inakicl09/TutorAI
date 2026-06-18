"""TutorAI prototype: a Socratic tutor powered by a local Ollama model.
Run this in iTerm with: python3 tutorprototype.py

This is the original command-line prototype, kept for quick testing
without Streamlit. See app.py for the full RAG-enabled version.
"""

import json
import urllib.request

import config
import prompts


def ask_ollama(conversation_history: list[dict]) -> str:
    """Send the conversation so far to Ollama and return the tutor's reply."""
    request_body = {
        "model": config.CHAT_MODEL_NAME,
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
    print("Type a question about any school subject.")
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
            tutor_reply = ask_ollama(conversation_history)
        except urllib.error.URLError:
            print("Tutor: I can't reach Ollama. Is it running? Try 'ollama serve'.")
            continue

        conversation_history.append({"role": "assistant", "content": tutor_reply})

        print(f"\nTutor: {tutor_reply}\n")


if __name__ == "__main__":
    main()
