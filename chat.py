"""Conversation logic: combines the Socratic prompt, retrieved course
material, and the Ollama model to produce the tutor's replies.
"""

import json
import urllib.request

import config
import prompts
import rag


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


def ask_tutor(
    conversation_history: list[dict],
    student_message: str,
    model_name: str = config.CHAT_MODEL_NAME,
) -> str:
    """Send the student's message to the tutor model, using relevant course
    material as extra context, and return the tutor's reply.

    `conversation_history` is updated in place with the plain student
    message and the tutor's reply, so the saved history stays readable.
    """
    relevant_chunks = rag.retrieve_relevant_chunks(student_message)
    context_prompt = prompts.build_context_prompt(relevant_chunks)

    conversation_history.append({"role": "user", "content": student_message})

    messages_for_model = conversation_history.copy()
    if context_prompt:
        messages_for_model[-1] = {
            "role": "user",
            "content": context_prompt + "\n\nStudent's message: " + student_message,
        }

    request_body = {
        "model": model_name,
        "messages": messages_for_model,
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

    tutor_reply = response_body["message"]["content"]
    conversation_history.append({"role": "assistant", "content": tutor_reply})

    return tutor_reply
