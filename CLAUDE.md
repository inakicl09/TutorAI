# TutorAI — Progress Notes

See `AGENTS.md` for coding style/conventions. This file tracks what's been
built and the current state of the project, for picking up work later.

## What this is

A Socratic tutoring app for Spanish secondary school students (1º ESO to
2º Bachillerato, Madrid LOMLOE curriculum), backed by a local Ollama model
(no cloud API key needed) with RAG over student-uploaded PDFs, and three
account types (student / teacher / admin) with role-based access.

Two interfaces share the same logic:
- `app.py` — Streamlit web UI (the main one, has the full teacher/admin
  dashboards).
- `tutor.py` — command-line prototype. Students can log in, link a
  teacher by join code, and chat. Teacher/admin accounts just get a
  message pointing them to the web app — building a parallel text UI for
  search/browse/dashboards wasn't worth it for a CLI test harness.

## Architecture

- `config.py` — Ollama URLs, model names, file paths, RAG chunk settings,
  the SQLite `DB_PATH`.
- `db.py` — single SQLite database (`data/tutorai.db`, gitignored).
  Tables: `users`, `teaching_assignments`, `subject_links`, `chats`,
  `chat_messages`, and a `tests` table that exists but is unused (see
  "Not yet built"). `init_db()` is safe to call every startup.
- `users.py` — signup/login plus the role system, all on top of `db.py`:
  - `create_student(username, password, grade)` / `create_teacher(...)`
    (returns a join code) / `create_admin(...)` (used only by
    `create_admin.py`, not exposed in any signup form).
  - Teachers declare `(grade, subject)` pairs they teach via
    `add_teaching_assignment`.
  - Students get access to a `(grade, subject)` only through
    `link_student_to_teacher`, which checks the teacher actually teaches
    it. This is what lets a student retake a subject at a lower grade —
    they just need a teacher linked for that specific grade+subject.
  - `find_teachers` (search by username), `find_teachers_for_subject_grade`
    (browse), `find_teacher_by_join_code` (the other linking path).
  - Passwords are hashed with `hashlib.pbkdf2_hmac` + a random per-user
    salt (`secrets.token_hex`), both stdlib — never stored in plain text.
- `create_admin.py` — one-time setup script you run yourself
  (`python3 create_admin.py`). Uses `getpass` so the password is never
  typed into chat or shell history. No other way to create an admin
  account exists.
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
- `chat_storage.py` — `create_chat(...)` inserts a chat + its system
  message, `add_message(chat_id, role, content)` appends one message,
  `load_chats(username)` rebuilds full history per chat. All SQLite, all
  on `db.py`.
- `app.py` — login/signup gate (role choice: student or teacher; no admin
  signup path), then branches by role:
  - **student**: sidebar has "link a teacher" (search by subject+grade,
    or enter a join code), "create chat" (only for grade+subject combos
    they're linked to), the chat list/switcher, model picker, PDF
    uploader. Each message is saved immediately via `chat_storage`.
  - **teacher**: shows their join code, a form to add more
    `(grade, subject)` teaching assignments, and a read-only view of
    every linked student's chats for subjects/grades they teach. Has a
    "Tests" section that's just a "coming soon" placeholder.
  - **admin**: lists every user and their role. Nothing more yet.
- `run.sh` — creates `.venv` and installs `requirements.txt` on first run,
  then launches `streamlit run app.py --server.headless true`.

## Setup already done on this machine

- Installed: streamlit, langchain, langchain-community, langchain-ollama,
  langchain-chroma, chromadb, pypdf (see `requirements.txt`).
- Pulled `nomic-embed-text` via `ollama pull` for embeddings.
- `ollama serve` must be running for either interface to work.
- No admin account exists yet — run `python3 create_admin.py` once to
  create one.

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
- Storage moved from a `data/users.json` + per-user chat JSON files to a
  single SQLite database (`data/tutorai.db`), specifically so chats,
  users, and the future tests feature all live in one place (user's
  explicit choice, mid-build — the JSON version was written and tested
  first, then replaced).
- Admin is pre-seeded via `create_admin.py`, not signup — "limited to
  myself" per the user. Teachers self-signup and self-declare which
  grade+subject pairs they teach (no admin approval step). Students link
  to teachers either by searching (subject+grade+username) or by join
  code — both paths were explicitly requested, not just one.
- Subject/grade names are kept as official Spanish curriculum terms in
  both language modes (not translated).

## Known gotcha (db.py / users.py / chat_storage.py)

`data/tutorai.db` is gitignored since it contains password hashes and
private chat content — don't remove it from `.gitignore`. There is no
migration script from the old JSON format; the JSON files were deleted
during the SQLite migration since no real user data existed yet.

## Not yet built

- The actual "create tests" feature for teachers — currently just a
  "coming soon" message. A `tests` table already exists in `db.py` for
  when this gets built.
- Per-chat model selection (currently one global model for all chats).
- Deleting/renaming chats, unlinking a student from a teacher.
- Any password reset/recovery flow (none exists — if a student forgets
  their password, there's currently no way to recover the account).
- Admin dashboard is read-only (just lists users) — no user management
  actions (delete, edit, promote) yet.
- `tutor.py` (CLI) has no path for a teacher to add teaching assignments
  or browse-search for students; only join-code linking works there, and
  only for students. Use the web app for the teacher/admin features.
