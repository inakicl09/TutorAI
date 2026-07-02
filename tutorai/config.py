"""Shared settings for TutorAI: model names, Groq API settings, and file paths."""

import os

# Groq API key, loaded from the GROQ_API_KEY environment variable (set in .env).
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Default chat model. All models below are available via Groq for free.
CHAT_MODEL_NAME = "llama-3.3-70b-versatile"

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
