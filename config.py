"""Shared settings for TutorAI: model names, Ollama URL, and file paths."""

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
CHAT_MODEL_NAME = "mistral"
EMBEDDING_MODEL_NAME = "nomic-embed-text"

DOCUMENTS_DIR = "data/documents"
CHROMA_DIR = "data/chroma_db"
DB_PATH = "data/tutorai.db"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
NUM_CHUNKS_TO_RETRIEVE = 4
