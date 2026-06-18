"""Conversation logic: combines the Socratic prompt, retrieved course
material, and the Ollama model to produce the tutor's replies.
"""

import json
import urllib.request

import config
import prompts
import rag


def ask_tutor(conversation_history: list[dict], student_message: str) -> str:
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
        "model": config.CHAT_MODEL_NAME,
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
