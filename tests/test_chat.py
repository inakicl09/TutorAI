"""chat.py talks to Ollama over the network, so these tests mock the
response instead of needing a real Ollama server running.
"""

import json
from unittest.mock import patch

from tutorai import chat


class FakeResponse:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_is_ollama_installed_reflects_whether_the_command_is_found():
    with patch("shutil.which", return_value="/usr/local/bin/ollama"):
        assert chat.is_ollama_installed() is True

    with patch("shutil.which", return_value=None):
        assert chat.is_ollama_installed() is False


def test_get_available_models_filters_out_the_embedding_model():
    fake_body = {
        "models": [
            {"name": "mistral"},
            {"name": "llama3"},
            {"name": "nomic-embed-text"},
        ]
    }

    with patch("urllib.request.urlopen", return_value=FakeResponse(fake_body)):
        available_models = chat.get_available_models()

    assert available_models == ["mistral", "llama3"]


def test_ask_assistant_appends_user_and_assistant_messages():
    conversation_history = [{"role": "system", "content": "system prompt"}]
    fake_body = {"message": {"role": "assistant", "content": "Here is a draft question..."}}

    with patch("urllib.request.urlopen", return_value=FakeResponse(fake_body)):
        reply = chat.ask_assistant(conversation_history, "Make me 3 questions about fractions")

    assert reply == "Here is a draft question..."
    assert conversation_history[1] == {
        "role": "user",
        "content": "Make me 3 questions about fractions",
    }
    assert conversation_history[2] == {"role": "assistant", "content": reply}


def test_ask_assistant_does_not_touch_rag(monkeypatch):
    """Logos and Artemis must never call into rag.py -- neither has
    document context."""
    from tutorai import rag

    def fail_if_called(*args, **kwargs):
        raise AssertionError("ask_assistant must not call rag.retrieve_relevant_chunks")

    monkeypatch.setattr(rag, "retrieve_relevant_chunks", fail_if_called)

    conversation_history = [{"role": "system", "content": "system prompt"}]
    fake_body = {"message": {"role": "assistant", "content": "ok"}}

    with patch("urllib.request.urlopen", return_value=FakeResponse(fake_body)):
        chat.ask_assistant(conversation_history, "hello")


def test_ask_logos_with_material_searches_the_teacher_materials_collection(monkeypatch):
    from tutorai import rag

    seen_calls = []

    def fake_retrieve(question, collection_name=None):
        seen_calls.append((question, collection_name))
        return ["Exam topic: fractions"]

    monkeypatch.setattr(rag, "retrieve_relevant_chunks", fake_retrieve)

    conversation_history = [{"role": "system", "content": "system prompt"}]
    fake_body = {"message": {"role": "assistant", "content": "Here's a question on fractions."}}

    with patch("urllib.request.urlopen", return_value=FakeResponse(fake_body)):
        reply = chat.ask_logos_with_material(conversation_history, "Make a question")

    assert seen_calls == [("Make a question", rag.TEACHER_MATERIALS_COLLECTION)]
    assert reply == "Here's a question on fractions."
    # the saved history keeps the plain message, not the injected context
    assert conversation_history[1] == {"role": "user", "content": "Make a question"}


def test_ask_logos_with_material_falls_back_when_nothing_relevant(monkeypatch):
    from tutorai import rag

    monkeypatch.setattr(rag, "retrieve_relevant_chunks", lambda *a, **k: [])

    conversation_history = [{"role": "system", "content": "system prompt"}]
    fake_body = {"message": {"role": "assistant", "content": "ok"}}

    with patch("urllib.request.urlopen", return_value=FakeResponse(fake_body)):
        chat.ask_logos_with_material(conversation_history, "hello")

    assert conversation_history[1] == {"role": "user", "content": "hello"}


def test_generate_structured_test_sends_a_user_message_not_system(monkeypatch):
    """A system-only conversation made Mistral ignore the format
    instructions entirely in manual testing -- this must stay a user
    message."""
    from tutorai import rag

    monkeypatch.setattr(rag, "retrieve_relevant_chunks", lambda *a, **k: [])

    captured_messages = []

    def fake_call(messages, model_name):
        captured_messages.extend(messages)
        return "QUESTION: ...\nA) 1\nB) 2\nC) 3\nD) 4\nCORRECT: A\n###"

    monkeypatch.setattr(chat, "_call_ollama_chat", fake_call)

    chat.generate_structured_test("1º ESO", "Matemáticas", "es", 3)

    assert len(captured_messages) == 1
    assert captured_messages[0]["role"] == "user"


def test_generate_structured_test_searches_teacher_materials(monkeypatch):
    from tutorai import rag

    seen_calls = []

    def fake_retrieve(question, collection_name=None):
        seen_calls.append((question, collection_name))
        return []

    monkeypatch.setattr(rag, "retrieve_relevant_chunks", fake_retrieve)

    fake_body = {"message": {"role": "assistant", "content": "ok"}}
    with patch("urllib.request.urlopen", return_value=FakeResponse(fake_body)):
        chat.generate_structured_test("1º ESO", "Matemáticas", "es", 3)

    assert seen_calls == [("Matemáticas exam questions", rag.TEACHER_MATERIALS_COLLECTION)]
