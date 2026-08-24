"""Shared settings for TutorAI: model names, Groq API settings, and file paths."""

import os

# Load .env from the project root so the API key is always available,
# regardless of whether the app is launched via run.sh or directly
# (e.g. from an IDE or VS Code). dotenv_values respects existing env
# vars -- if GROQ_API_KEY is already set (e.g. by run.sh), it stays.
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    load_dotenv(_env_path, override=False)
except ImportError:
    pass  # python-dotenv not installed; rely on run.sh to export the key

# Groq API key, loaded from the GROQ_API_KEY environment variable (set in .env).
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Default chat model. All models below are available via Groq for free.
CHAT_MODEL_NAME = "openai/gpt-oss-120b"

# Embedding model used by sentence-transformers for RAG (runs locally, no API key needed).
# Downloaded automatically the first time it's used (~22 MB).
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

DOCUMENTS_DIR = "data/documents"
CHROMA_DIR = "data/chroma_db"
DB_PATH = "data/tutorai.db"

# Key used to let the admin view a user's actual password (see crypto.py).
# Generated on first use if missing. Never commit this file -- whoever
# holds it can decrypt every stored password.
SECRET_KEY_PATH = "data/secret.key"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
NUM_CHUNKS_TO_RETRIEVE = 4

# Display name shown to each role once logged in.
ASSISTANT_NAMES = {
    "student": "Socrates",
    "teacher": "Logos",
    "admin": "Artemis",
}
