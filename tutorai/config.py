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

# --- Public test site (a second Streamlit Cloud app on the same repo) ---
# Switched on only by setting the TUTORAI_PUBLIC_TEST = "1" secret. Off
# everywhere else (local runs, the full demo), which behave as before.
PUBLIC_TEST_MODE = os.environ.get("TUTORAI_PUBLIC_TEST", "") == "1"
PUBLIC_TEST_TEACHER_USERNAME = "profesor_tutorai"
PUBLIC_TEST_ADMIN_USERNAME = "admin"
# Private passwords for the site owner's own accounts on the test site.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
TEACHER_PASSWORD = os.environ.get("TEACHER_PASSWORD", "")
# How testers can contact the person running the research project, shown
# in the privacy notice (e.g. an email). Optional.
RESEARCH_CONTACT = os.environ.get("RESEARCH_CONTACT", "")
# On this date (UTC calendar day) every tester's data on the public test
# site is deleted automatically and the site closes (see project_end.py).
# The user chose 30 June 2027; the privacy notice quotes it.
PROJECT_END_DATE = os.environ.get("PROJECT_END_DATE", "2027-06-30")
# Bump when the privacy notice text changes: it's stored with each
# tester's consent, to show which version they accepted.
PRIVACY_NOTICE_VERSION = "2026-11-24b"  # b: states the automatic deletion date
# Link to the external feedback questionnaire, shown as a button if set.
FEEDBACK_FORM_URL = os.environ.get("FEEDBACK_FORM_URL", "")
# In test mode only the last this-many chat messages (plus the system
# prompt) are sent to Groq, to stretch the free tokens-per-minute quota.
PUBLIC_TEST_MAX_HISTORY_MESSAGES = 20

# Fernet key for crypto.py. If set, it's used instead of SECRET_KEY_PATH --
# needed on hosts whose disk is wiped on restart, or a restored database's
# encrypted passwords could never be decrypted again.
SECRET_KEY = os.environ.get("SECRET_KEY", "")

# Supabase Storage, where persistence.py backs up the SQLite file. All
# three must be set, otherwise persistence is off.
def clean_supabase_url(url: str) -> str:
    """Accept the project URL even if it was copied with the REST API path
    (https://xxxx.supabase.co/rest/v1/) -- only the base is wanted."""
    url = url.strip().rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    return url


SUPABASE_URL = clean_supabase_url(os.environ.get("SUPABASE_URL", ""))
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "")

# Display name shown to each role once logged in.
ASSISTANT_NAMES = {
    "student": "Socrates",
    "teacher": "Logos",
    "admin": "Artemis",
}
