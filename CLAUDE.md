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
- `app.py` — Streamlit UI: language + grade + subject pickers, "create
  chat" button that starts a new conversation thread, a list of chats to
  switch between (multi-chat, session-only — not saved to disk yet),
  model picker, PDF uploader.
- `tutor.py` — CLI equivalent of the same flow (no multi-chat there, just
  one conversation per run, since multi-chat is a UI concept).
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
- Multi-chat is session-only for now; explicitly deferred: "later we will
  add memory and users that can log in" — i.e. persistence and accounts
  are a known future step, not yet built.
- Subject/grade names are kept as official Spanish curriculum terms in
  both language modes (not translated).

## Not yet built

- Persisting chats across app restarts (deferred per above).
- User accounts/login.
- Per-chat model selection (currently one global model for all chats).
- Deleting/renaming chats.
