# TutorAI — Progress Notes

See `AGENTS.md` for coding style/conventions. This file tracks what's been
built and the current state of the project, for picking up work later.

## What this is

A Socratic tutoring app for Spanish secondary school students (1º ESO to
2º Bachillerato, Madrid LOMLOE curriculum), backed by a local Ollama model
(no cloud API key needed) with RAG over student-uploaded PDFs, and three
account types (student / teacher / admin) with role-based access.

Two interfaces share the same logic:
- `tutorai/app.py` — Streamlit web UI (the main one, has the full
  teacher/admin dashboards).
- `tutorai/tutor.py` — command-line prototype. Students can log in, link
  a teacher by join code, and chat. Teacher/admin accounts just get a
  message pointing them to the web app — building a parallel text UI for
  search/browse/dashboards wasn't worth it for a CLI test harness.

## Architecture

All app code lives in the `tutorai/` package (flat — no sub-packages),
with a `tests/` directory alongside it (see "Testing" below). Modules
import each other with absolute imports, e.g. `from tutorai import db`.

- `config.py` — Ollama URLs, model names, file paths, RAG chunk settings,
  the SQLite `DB_PATH`.
- `db.py` — single SQLite database (`data/tutorai.db`, gitignored).
  Tables: `users`, `classes`, `teaching_assignments`, `subject_links`,
  `chats`, `chat_messages`, and a `tests` table that exists but is unused
  (see "Not yet built"). `init_db()` is safe to call every startup.
- `classes.py` — one classroom group per grade (e.g. "1º ESO - A"), only
  one class per grade for now. `ensure_default_classes()` creates the six
  classes if missing and backfills `class_id` for any student who
  predates this feature; called right after `db.init_db()` in every
  entry point (`app.py`, `tutor.py`, `create_admin.py`,
  `seed_test_data.py`, and the test fixture).
- `users.py` — signup/login plus the role system, all on top of `db.py`:
  - `create_student(username, password, grade)` (auto-assigned to that
    grade's class) / `create_teacher(...)` (returns a join code) /
    `create_admin(...)` (used only by `create_admin.py`, not exposed in
    any signup form).
  - Teachers declare `(grade, subject)` pairs they teach via
    `add_teaching_assignment`.
  - Students get access to a `(grade, subject)` only through
    `link_student_to_teacher`, which checks both that the teacher
    actually teaches it AND that the grade is the student's own grade or
    exactly one grade below (`allowed_link_grades`) — never further. This
    is what lets a student retake a subject at a lower grade, without
    letting their subjects span the whole curriculum. `seed_test_data.py`
    has a `fix_invalid_subject_links()` cleanup pass for links created
    before this rule existed.
  - `find_teachers` (search by username, alphabetical), `list_all_users`
    (search by username, alphabetical, no password data),
    `find_teacher_by_join_code` (the other linking path), and
    `unlink_student_from_teacher` (the inverse of linking).
  - Passwords are hashed with `hashlib.pbkdf2_hmac` + a random per-user
    salt (`secrets.token_hex`), both stdlib — never stored in plain text.
- `create_admin.py` — one-time setup script you run yourself
  (`python3 -m tutorai.create_admin`). Uses `getpass` so the password is
  never typed into chat or shell history. No other way to create an
  admin account exists.
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
  - **admin**: can add a student or teacher account, browse students
    grouped by class+grade (`classes.list_classes` /
    `classes.students_in_class`), search/list every user alphabetically,
    view a teacher's full teaching list or a student's full link list
    (with per-link remove buttons and an admin-initiated link form),
    change anyone's password (the password-recovery mechanism, since
    there's no self-service flow), regenerate a teacher's join code, and
    delete a user (with a confirm/cancel step first). Deleting a user
    cascades: their chats+messages, teaching assignments, and
    subject_links in either direction all get cleaned up
    (`users.delete_user`). Can't delete your own logged-in account.
    Admin accounts themselves still can't be created from the UI — only
    via `create_admin.py`, per the "limited to myself" requirement.
- `run.sh` — creates `.venv` and installs `requirements.txt` on first run,
  then launches `python -m streamlit run tutorai/app.py --server.headless
  true`. Using `python -m streamlit` (not the bare `streamlit` command)
  is what puts the repo root on `sys.path` so `tutorai/app.py`'s
  `from tutorai import ...` imports resolve.

## Testing

- `tests/` mirrors `tutorai/` module-by-module (`tests/test_users.py`
  tests `tutorai/users.py`, etc.), using `pytest`.
- `tests/conftest.py` has an autouse fixture that points `config.DB_PATH`
  at a temp file and calls `db.init_db()` before every test, so the test
  suite never touches `data/tutorai.db`.
- `rag.py` isn't unit tested — it needs a real Ollama embedding model
  running, which isn't worth mocking for this project's size. `chat.py`'s
  pure logic (filtering the embedding model out of `get_available_models`)
  is tested with a mocked `urlopen`; `ask_tutor` (which also hits RAG) is
  not.
- Run with: `pip install -r requirements-dev.txt && pytest`.

## Setup already done on this machine

- Installed: streamlit, langchain, langchain-community, langchain-ollama,
  langchain-chroma, chromadb, pypdf (see `requirements.txt`).
- Pulled `nomic-embed-text` via `ollama pull` for embeddings.
- `ollama serve` must be running for either interface to work.
- No admin account exists yet — run `python3 -m tutorai.create_admin`
  once to create one.

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
  to teachers either by searching by username (seeing every matching
  teacher's full subject list) or by join code — both paths were
  explicitly requested, not just one.
- Subject/grade names are kept as official Spanish curriculum terms in
  both language modes (not translated).
- A student's subject links are capped at their own grade or exactly one
  grade below (`users.allowed_link_grades`) — added after the user
  noticed seeded students had subjects spanning very distant grades,
  which didn't reflect a realistic "retaking one subject" scenario.
- Classes are modeled as a real table (one per grade for now) rather
  than just grouping by the existing `grade` column, since the user
  asked for "classes" as their own concept — anticipating multiple
  classes per grade later without a data model change.
- Moved all modules from flat root-level files into a `tutorai/` package
  plus a `tests/` directory with `pytest` coverage (user's explicit
  choice, 2026-06-20, overriding `AGENTS.md`'s earlier "keep it flat, no
  package structure" guidance — `AGENTS.md` has been updated to match).
  Entry-point scripts are now run as `python3 -m tutorai.<name>`, and the
  Streamlit app as `python -m streamlit run tutorai/app.py`, instead of
  as bare scripts, so the package's absolute imports resolve.

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
- Self-service password reset still doesn't exist, but admin can now
  reset any user's password from the dashboard as a workaround.
- Admin can't change a user's role (e.g. promote student to teacher) or
  create another admin from the UI — delete+recreate is the only path,
  and admin creation stays exclusively in `create_admin.py`.
- `tutor.py` (CLI) has no path for a teacher to add teaching assignments,
  browse-search for students, or any of the new admin actions (add/
  delete user, change password, regenerate join code) — only student
  login + join-code linking works there. Use the web app for everything
  else.
