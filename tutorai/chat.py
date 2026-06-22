"""Conversation logic: combines the Socratic prompt, retrieved course
material, and the Ollama model to produce the tutor's replies. Also
talks to Logos (teacher), which can optionally use a teacher's uploaded
exam material as RAG context, and Artemis (admin), which never uses RAG.
"""

import json
import shutil
import urllib.request

from tutorai import config, prompts, rag


def is_ollama_installed() -> bool:
    """Check whether the `ollama` command exists on this machine, so we
    can tell a "not installed" error apart from "installed but not
    running right now"."""
    return shutil.which("ollama") is not None


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


def _call_ollama_chat(messages: list[dict], model_name: str) -> str:
    """POST a list of messages to Ollama's /api/chat and return the
    reply's content."""
    request_body = {
        "model": model_name,
        "messages": messages,
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

    tutor_reply = _call_ollama_chat(messages_for_model, model_name)
    conversation_history.append({"role": "assistant", "content": tutor_reply})

    return tutor_reply


def ask_assistant(
    conversation_history: list[dict],
    message: str,
    model_name: str = config.CHAT_MODEL_NAME,
) -> str:
    """Send a message to Logos or Artemis and return the reply, with no
    RAG step. Used by Artemis always, and by Logos when there's no
    uploaded exam material to search (see ask_logos_with_material).
    `conversation_history` is updated in place, same as ask_tutor.
    """
    conversation_history.append({"role": "user", "content": message})
    reply = _call_ollama_chat(conversation_history, model_name)
    conversation_history.append({"role": "assistant", "content": reply})

    return reply


def ask_logos_with_material(
    conversation_history: list[dict],
    teacher_message: str,
    model_name: str = config.CHAT_MODEL_NAME,
) -> str:
    """Send the teacher's message to Logos, using any exam material
    they've uploaded as extra context (rag.TEACHER_MATERIALS_COLLECTION).

    Mirrors ask_tutor's RAG step, but over the teacher's own material
    instead of the student's course documents -- the two are kept in
    separate chromaDB collections so a teacher's exam content never
    leaks into a student's tutoring session. If nothing's been uploaded
    (or nothing relevant is found), this behaves just like ask_assistant.
    """
    relevant_chunks = rag.retrieve_relevant_chunks(
        teacher_message, collection_name=rag.TEACHER_MATERIALS_COLLECTION
    )
    context_prompt = prompts.build_material_context_prompt(relevant_chunks)

    conversation_history.append({"role": "user", "content": teacher_message})

    messages_for_model = conversation_history.copy()
    if context_prompt:
        messages_for_model[-1] = {
            "role": "user",
            "content": context_prompt + "\n\nTeacher's message: " + teacher_message,
        }

    reply = _call_ollama_chat(messages_for_model, model_name)
    conversation_history.append({"role": "assistant", "content": reply})

    return reply


def generate_structured_test(
    grade: str,
    subject: str,
    language: str,
    num_questions: int,
    model_name: str = config.CHAT_MODEL_NAME,
) -> str:
    """One-shot generation of a multiple-choice test (not an ongoing
    chat), using any uploaded exam material as RAG context. Returns the
    raw model text -- parse it with exams.parse_structured_test before
    publishing, since local models don't always follow the format
    exactly.

    Sent as a "user" message, not "system" -- a system-only conversation
    (no user turn at all) made Mistral via Ollama ignore the formatting
    instructions entirely and emit unrelated training-data-like snippets
    instead, even though the exact same text as a user message worked
    reliably.
    """
    relevant_chunks = rag.retrieve_relevant_chunks(
        f"{subject} exam questions", collection_name=rag.TEACHER_MATERIALS_COLLECTION
    )
    material_context = prompts.build_material_context_prompt(relevant_chunks)
    structured_prompt = prompts.build_structured_test_prompt(
        grade, subject, language, num_questions, material_context
    )
    return _call_ollama_chat([{"role": "user", "content": structured_prompt}], model_name)
