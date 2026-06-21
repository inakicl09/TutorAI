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


def test_ask_logos_appends_user_and_assistant_messages():
    conversation_history = [{"role": "system", "content": "system prompt"}]
    fake_body = {"message": {"role": "assistant", "content": "Here is a draft question..."}}

    with patch("urllib.request.urlopen", return_value=FakeResponse(fake_body)):
        reply = chat.ask_logos(conversation_history, "Make me 3 questions about fractions")

    assert reply == "Here is a draft question..."
    assert conversation_history[1] == {
        "role": "user",
        "content": "Make me 3 questions about fractions",
    }
    assert conversation_history[2] == {"role": "assistant", "content": reply}


def test_ask_logos_does_not_touch_rag(monkeypatch):
    """Logos must never call into rag.py -- it has no document context."""
    from tutorai import rag

    def fail_if_called(*args, **kwargs):
        raise AssertionError("ask_logos must not call rag.retrieve_relevant_chunks")

    monkeypatch.setattr(rag, "retrieve_relevant_chunks", fail_if_called)

    conversation_history = [{"role": "system", "content": "system prompt"}]
    fake_body = {"message": {"role": "assistant", "content": "ok"}}

    with patch("urllib.request.urlopen", return_value=FakeResponse(fake_body)):
        chat.ask_logos(conversation_history, "hello")
