# TutorAI — Progress Notes

See `AGENTS.md` for coding style/conventions. This file tracks what's been
built and the current state of the project, for picking up work later.

## What this is

A Socratic tutoring app for Spanish secondary school students (1º ESO to
2º Bachillerato, Madrid LOMLOE curriculum), backed by a local Ollama model
(no cloud API key needed) with RAG over student-uploaded PDFs.

Two interfaces share the same logic:
- `app.py` — Streamlit web UI (the main one).
- `tutor.py` — command-line prototype, kept for quick testing without
  Streamlit.

## Architecture

- `config.py` — Ollama URLs, model names, file paths, RAG chunk settings.
- `subjects.py` — official grade → subject list (39 distinct subjects
  across 6 grades, from the Madrid LOMLOE curriculum).
- `prompts.py` — builds each system prompt from three pieces: a
  subject-specific focus (`SUBJECT_FOCUS`, one entry per distinct subject),
  a grade difficulty calibration (`GRADE_INSTRUCTIONS`, one per grade), and
  a response-language instruction (`LANGUAGE_INSTRUCTIONS`). This avoids
  hand-writing ~70 near-duplicate prompts for every grade+subject pair.
- `translations.py` — UI strings in Spanish/English for both `app.py` and
  `tutor.py`. Subject and grade names are NOT translated (they're official
  curriculum names, shown as-is regardless of UI language).
- `rag.py` — PDF ingestion (chunk + embed with `nomic-embed-text` via
  Ollama) and retrieval, persisted in chromaDB at `data/chroma_db`.
- `chat.py` — calls Ollama's `/api/chat`, combines retrieved chunks into
  the prompt context, lists available models via `/api/tags` (filtering
  out the embedding-only model since it can't chat).
- `users.py` — signup/login. Accounts stored in `data/users.json`
  (gitignored). Passwords are never stored in plain text: each one is
  hashed with `hashlib.pbkdf2_hmac` and a random per-user salt
  (`secrets.token_hex`), both stdlib.
- `chat_storage.py` — loads/saves each user's chats as
  `data/chats/<username>.json` (gitignored), so chats survive restarts.
- `app.py` — Streamlit UI: login/signup gate first, then language + grade
  + subject pickers, "create chat" button that starts a new conversation
  thread, a list of chats to switch between (multi-chat), model picker,
  PDF uploader. Chats are saved to disk after every new chat and every
  tutor reply.
- `tutor.py` — CLI equivalent: login/signup, then grade/subject/model
  pickers, one conversation per run. Each run's conversation is appended
  to the user's saved chats on disk (no multi-chat switching in the CLI,
  since that's a UI concept, but history does accumulate across runs).
- `run.sh` — creates `.venv` and installs `requirements.txt` on first run,
  then launches `streamlit run app.py --server.headless true`.

## Setup already done on this machine

- Installed: streamlit, langchain, langchain-community, langchain-ollama,
  langchain-chroma, chromadb, pypdf (see `requirements.txt`).
- Pulled `nomic-embed-text` via `ollama pull` for embeddings.
- `ollama serve` must be running for either interface to work.

## Known gotcha (fixed)

`run.sh` used to call plain `streamlit run app.py`. On a machine that has
never run Streamlit before, Streamlit blocks on an interactive "enter your
email" welcome prompt the first time — invisible/silent when launched from
a script instead of a terminal, looking like the script "does nothing."
Fixed by adding `--server.headless true`, which skips that prompt
entirely. Verified by removing `~/.streamlit/credentials.toml` and
confirming `./run.sh` still starts cleanly.

## Decisions made along the way

- One prompt per subject + a shared grade modifier, not ~70 fully
  separate prompts (user's choice, for maintainability).
- Login is username/password (not pre-issued access codes), accounts
  stored in a JSON file (not SQLite), and chats are saved to disk per
  user (not session-only) — all per user's explicit choice.
- Subject/grade names are kept as official Spanish curriculum terms in
  both language modes (not translated).

## Known gotcha (users.py / chat_storage.py)

`data/users.json` and `data/chats/` are gitignored since they contain
password hashes and private chat content — don't remove them from
`.gitignore`.

## Not yet built

- Per-chat model selection (currently one global model for all chats).
- Deleting/renaming chats.
- Any password reset/recovery flow (none exists — if a student forgets
  their password, there's currently no way to recover the account).
