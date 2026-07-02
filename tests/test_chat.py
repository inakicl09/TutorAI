"""chat.py talks to Groq over the network, so these tests mock the
client instead of needing a real API connection.
"""

from unittest.mock import MagicMock, patch

from tutorai import chat


def make_fake_completion(content: str):
    """Build a fake OpenAI-style completion response with the given content."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


def test_is_api_key_configured_returns_true_when_key_is_set(monkeypatch):
    monkeypatch.setattr(chat.config, "GROQ_API_KEY", "fake-key")
    assert chat.is_api_key_configured() is True


def test_is_api_key_configured_returns_false_when_key_is_empty(monkeypatch):
    monkeypatch.setattr(chat.config, "GROQ_API_KEY", "")
    assert chat.is_api_key_configured() is False


def test_get_available_models_returns_a_non_empty_list():
    models = chat.get_available_models()
    assert len(models) > 0
    assert all(isinstance(m, str) for m in models)


def test_ask_assistant_appends_user_and_assistant_messages():
    conversation_history = [{"role": "system", "content": "system prompt"}]

    with patch("tutorai.chat._client") as mock_client:
        mock_client.chat.completions.create.return_value = make_fake_completion(
            "Here is a draft question..."
        )
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

    with patch("tutorai.chat._client") as mock_client:
        mock_client.chat.completions.create.return_value = make_fake_completion("ok")
        chat.ask_assistant(conversation_history, "hello")


def test_ask_logos_with_material_searches_the_teacher_materials_collection(monkeypatch):
    from tutorai import rag

    seen_calls = []

    def fake_retrieve(question, collection_name=None):
        seen_calls.append((question, collection_name))
        return ["Exam topic: fractions"]

    monkeypatch.setattr(rag, "retrieve_relevant_chunks", fake_retrieve)

    conversation_history = [{"role": "system", "content": "system prompt"}]

    with patch("tutorai.chat._client") as mock_client:
        mock_client.chat.completions.create.return_value = make_fake_completion(
            "Here's a question on fractions."
        )
        reply = chat.ask_logos_with_material(conversation_history, "Make a question")

    assert seen_calls == [("Make a question", rag.TEACHER_MATERIALS_COLLECTION)]
    assert reply == "Here's a question on fractions."
    # the saved history keeps the plain message, not the injected context
    assert conversation_history[1] == {"role": "user", "content": "Make a question"}


def test_ask_logos_with_material_falls_back_when_nothing_relevant(monkeypatch):
    from tutorai import rag

    monkeypatch.setattr(rag, "retrieve_relevant_chunks", lambda *a, **k: [])

    conversation_history = [{"role": "system", "content": "system prompt"}]

    with patch("tutorai.chat._client") as mock_client:
        mock_client.chat.completions.create.return_value = make_fake_completion("ok")
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

    monkeypatch.setattr(chat, "_call_groq_chat", fake_call)

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

    with patch("tutorai.chat._client") as mock_client:
        mock_client.chat.completions.create.return_value = make_fake_completion("ok")
        chat.generate_structured_test("1º ESO", "Matemáticas", "es", 3)

    assert seen_calls == [("Matemáticas exam questions", rag.TEACHER_MATERIALS_COLLECTION)]
