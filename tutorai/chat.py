"""Conversation logic: combines the Socratic prompt, retrieved course
material, and the Groq API to produce the tutor's replies. Also
talks to Logos (teacher), which can optionally use a teacher's uploaded
exam material as RAG context, and Artemis (admin), which never uses RAG.
"""

from openai import OpenAI

from tutorai import config, prompts, rag

# One shared client for the whole app -- the OpenAI SDK is thread-safe
# and Groq uses the same API format as OpenAI. Created lazily on first
# use rather than at import time: the OpenAI constructor raises when the
# API key is missing, which would make `import tutorai.chat` itself crash
# in any environment without GROQ_API_KEY set (pytest, scripts). The app
# checks is_api_key_configured() and shows its own error instead.
_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL)
    return _client


def is_api_key_configured() -> bool:
    """Return True if the Groq API key has been set in the environment."""
    return bool(config.GROQ_API_KEY)


def get_available_models() -> list[str]:
    """Fetch the chat models actually available on this Groq account.

    Filters to only the models this app is designed to work with, so the
    dropdown never shows a model the account doesn't have access to (which
    would cause a misleading "not connected" error on the first message).
    Falls back to a safe default list if the API call itself fails.
    """
    supported = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
    ]
    try:
        response = _get_client().models.list()
        available_ids = {m.id for m in response.data}
        live = [m for m in supported if m in available_ids]
        return live if live else [supported[0]]
    except Exception:
        return [supported[0]]


def _call_groq_chat(messages: list[dict], model_name: str) -> str:
    """Send a list of messages to Groq and return the reply text."""
    response = _get_client().chat.completions.create(
        model=model_name,
        messages=messages,
    )
    return response.choices[0].message.content


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

    tutor_reply = _call_groq_chat(messages_for_model, model_name)
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
    reply = _call_groq_chat(conversation_history, model_name)
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
    separate chromaDB collections so a teacher's exam content can never
    leak into a student's tutoring session. If nothing's been uploaded
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

    reply = _call_groq_chat(messages_for_model, model_name)
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
    publishing, since models don't always follow the format exactly.

    Sent as a "user" message, not "system" -- a system-only conversation
    (no user turn at all) made Mistral via Ollama ignore the formatting
    instructions entirely and emit unrelated snippets instead, even though
    the exact same text as a user message worked reliably.
    """
    relevant_chunks = rag.retrieve_relevant_chunks(
        f"{subject} exam questions", collection_name=rag.TEACHER_MATERIALS_COLLECTION
    )
    material_context = prompts.build_material_context_prompt(relevant_chunks)
    structured_prompt = prompts.build_structured_test_prompt(
        grade, subject, language, num_questions, material_context
    )
    return _call_groq_chat([{"role": "user", "content": structured_prompt}], model_name)
