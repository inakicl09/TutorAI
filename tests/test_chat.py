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
