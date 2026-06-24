# TutorAI — Progress Notes

See `AGENTS.md` for coding style/conventions. This file tracks what's been
built and the current state of the project, for picking up work later.

## ⚠️ TEMPORARY: dev-only login shortcut

`app.py`'s login screen has a "log in as any user, no password" dropdown
below the normal login/signup form, clearly marked with
`# --- TEMPORARY ---` comments in the code. The user explicitly asked
for this purely for testing different roles quickly, and said to remove
it once the project is finished. **Remove that block (and the
`dev_login_*` translation keys) before any real deployment** — anyone
who opens the app can otherwise log in as anyone, including Admin,
without a password.

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
  Tables: `users`, `homerooms`, `classes`, `teaching_assignments`,
  `subject_links`, `chats`, `chat_messages`, and a `tests` table that
  exists but is unused (see "Not yet built"). `init_db()` is safe to call
  every startup, and migrates older databases (adds `created_at` to
  `chat_messages`; renames the old grade-only `classes` table to
  `homerooms` and creates the new `classes` table; adds
  `users.homeroom_id` and copies it from the old `class_id`, which is
  left in place unused rather than risking an unsupported DROP COLUMN).
- Two distinct "class" concepts, on purpose (the first design only had
  the second one, then got corrected mid-build):
  - `classes.py` — a class is one teacher's group for one grade+subject
    (e.g. "Matemáticas - 3º ESO" taught by profesor_lopez). A student is
    "in" a class once linked to that teacher for that grade+subject —
    there's no separate enrollment table, since `subject_links` already
    describes that relationship. `get_or_create_class` is called from
    `users.add_teaching_assignment`; `sync_with_teaching_assignments()`
    backfills classes for assignments that predate this table, called
    right after `db.init_db()` in every entry point.
  - `homerooms.py` — a homeroom is a grade-level administrative group
    capped at `MAX_STUDENTS_PER_HOMEROOM` (30), e.g. "1º ESO - A" then
    "1º ESO - B" once "A" is full. Unrelated to subjects/teachers. Every
    student belongs to exactly one, assigned by `assign_homeroom` inside
    `users.create_student`. `backfill_homerooms()` places any student
    missing one, called right after `db.init_db()` in every entry point.
- `users.py` — signup/login plus the role system, all on top of `db.py`:
  - `create_student(username, password, grade)` (auto-assigned to a
    homeroom) / `create_teacher(...)` (returns a join code) /
    `create_admin(...)` (used only by `create_admin.py`, not exposed in
    any signup form).
  - Teachers declare `(grade, subject)` pairs they teach via
    `add_teaching_assignment` (also creates the matching class).
  - Students get access to a `(grade, subject)` only through
    `link_student_to_teacher`, which checks both that the teacher
    actually teaches it AND that the grade is the student's own grade or
    exactly one grade below (`allowed_link_grades`) — never further. This
    is what lets a student retake a subject at a lower grade, without
    letting their subjects span the whole curriculum. `seed_test_data.py`
    has a `fix_invalid_subject_links()` cleanup pass for links created
    before this rule existed.
  - `find_teachers` (search by username, alphabetical), `list_all_users`
    (search by username, alphabetical, optional role filter, no password
    data), `find_teacher_by_join_code` (the other linking path), and
    `unlink_student_from_teacher` (the inverse of linking).
  - Logins are verified against a PBKDF2 hash (`hashlib.pbkdf2_hmac` +
    a random per-user salt via `secrets.token_hex`, both stdlib) — that
    hash is never reversed. Separately, `crypto.py` stores each password
    in a *reversibly encrypted* form too, purely so `get_plaintext_password`
    can give the admin dashboard a "view password" feature — see the
    security note below.
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
  Takes an optional `collection_name`: student course material uses the
  default collection, teacher exam material uses a separate one
  (`TEACHER_MATERIALS_COLLECTION`), so the two can never mix.
- `chat.py` — calls Ollama's `/api/chat`, combines retrieved chunks into
  the prompt context, lists available models via `/api/tags` (filtering
  out the embedding-only model since it can't chat). `is_ollama_installed()`
  uses `shutil.which("ollama")` to tell "not installed" apart from
  "installed but not running" when the connection fails, so the error
  message can point to https://ollama.com/download specifically when
  needed. `tutor.py` duplicates this one check (not the rest of chat.py)
  to stay independent of `rag.py`'s heavier imports.
- `chat_storage.py` — `create_chat(..., mode=None)` inserts a chat + its
  system message (`mode` is "draft"/"analyze" for Logos chats, NULL
  otherwise), `add_message(chat_id, role, content)` appends one message,
  `load_chats(username)` rebuilds full history per chat (`mode` included).
  All SQLite, all on `db.py`. Reused as-is for both Socrates (student)
  and Logos (teacher) conversations -- the schema doesn't care which
  role owns a chat, so no changes were needed to support Logos.
- `exams.py` — `save_test`/`list_tests_for_teacher`/`delete_test` on the
  `tests` table (now has a `content` column, migrated in `db.py`).
  Deliberately not named `tests.py`, so it doesn't read like the
  project's pytest suite (`tests/`, no `__init__.py`, just a sibling
  directory -- not an actual import collision, but a human-confusion one).
- `app.py` — login/signup gate (role choice: student or teacher; no admin
  signup path). Once logged in, the sidebar (below the logged-in-as/logout
  controls) has a `st.radio` screen picker, `SCREENS_BY_ROLE`, so each
  role's dashboard is several sidebar-navigable screens instead of one
  long scrolling page. The persona name (`config.ASSISTANT_NAMES[role]`)
  is always the page title regardless of which screen is active.
  - **student** (Socrates): *Main menu* (welcome, grade, homeroom,
    linked-classes/chats-started stats), *Chat* (create/switch chats for
    grade+subject combos they're linked to, model picker, the
    conversation itself — each message saved immediately via
    `chat_storage`), *Link teacher* (search by username or join code),
    *Material* (PDF upload for RAG), *Exámenes* (every published test
    for a class they're linked to: "Start test" renders the multiple-
    choice questions with radio buttons, "Submit" grades immediately via
    `exams.submit_test` and shows the score; one attempt per student per
    test, enforced by a UNIQUE constraint on `test_submissions`. Already-
    completed tests just show the stored score instead of the form),
    *Tarjetas* (flashcards): one auto-created per wrong answer at
    submission time (`exams.submit_test`, no LLM involved -- just the
    question text + the correct option's text), with a reveal-then-"Got
    it" flow that deletes the card once the student feels confident.
  - **teacher** (Logos): *Main menu* (welcome, join code, classes-taught/
    students-linked/tests-saved stats), *Supervise students* (read-only
    view of every linked student's chats, with message-count and
    last-active per student), *My classes* (add/list `(grade, subject)`
    teaching assignments), *Logos* (sidebar tab; was "Tests" until the
    user pointed out it should say the assistant's name):
    - A PDF uploader for exam material (own chromaDB collection,
      `rag.TEACHER_MATERIALS_COLLECTION`, kept separate from students'
      course material so exam content can never leak into a student's
      tutoring session). Worded with `prompts.build_material_context_prompt`
      (not `build_context_prompt`, which says "the student's course
      documents" -- wrong framing for a teacher's own material).
    - An open-ended chat with a mode switch when starting a new one:
      "Draft a test" (`prompts.build_logos_system_prompt`, then an
      auto-sent opening message via `chat.ask_logos_with_material` so
      the teacher sees a generated exam immediately instead of an empty
      chat) or "Analyze student struggles" (`build_class_activity_summary`
      gathers the linked students' chat history for that class, baked
      into `prompts.build_logos_analysis_prompt`, opening message via
      plain `chat.ask_assistant`). Each chat's `mode` ("draft"/"analyze")
      is persisted on the `chats` row and checked on every later message
      too, so an "analyze" chat never mixes in exam-material RAG context
      meant only for drafting, and a "draft" chat keeps using it.
      "Save as test" persists the latest reply as freeform text via
      `exams.save_test` -- good for printing, not completable by
      students.
    - A separate "Generate a test for your students" flow: pick a class
      and a question count, `chat.generate_structured_test` makes a
      *one-shot* call (not part of the chat above) using
      `prompts.build_structured_test_prompt`, a strict QUESTION/A-D/CORRECT
      format with a literal `###` separator between questions, parsed by
      `exams.parse_structured_test` (regex-based, tolerant of stray
      whitespace; returns whatever it can find, since a small local
      model doesn't always comply perfectly -- the UI shows "N of M
      parsed" so the teacher can just regenerate if too few came back).
      The parsed preview can then be published (`exams.publish_test`),
      which creates `test_questions` rows and makes the test visible to
      every student linked to that teacher for that grade+subject.
      Published tests are listed with live submission counts/scores.
  - **admin** (Artemis): *Main menu* (total students/teachers/classes/
    homerooms stats), *Add user* (student or teacher), *Teachers* menu
    (filter by grade, search by username), *Students* menu (filter by
    grade, filter by class, search by username — filters apply together
    with AND logic), *Artemis* (a single persistent chat, no RAG, no
    grade/subject — `prompts.build_artemis_system_prompt` /
    `chat.ask_assistant`; the chats table needs a non-null grade/subject
    so this uses the sentinel values `"Admin"`/`"Artemis"`, set once in
    `app.py`). Teacher/student entries show full teaching/link
    lists (with per-link remove buttons and an admin-initiated link
    form), the actual password (see the security note below), plus
    shared password-change and delete-with-confirm controls
    (`render_change_password_and_delete`, used by both menus). Deleting
    a user cascades: their chats+messages, teaching assignments, classes
    they teach, and subject_links in either direction all get cleaned
    up (`users.delete_user`). Can't delete your own logged-in account.
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
- `app.py` itself has no pytest coverage (it's all Streamlit calls, not
  pure functions) — when restructuring its screens, it was instead
  smoke-tested with `streamlit.testing.v1.AppTest`: log in as each role
  by setting `at.session_state["username"]` directly (clicking through
  the actual login form tripped an AppTest harness quirk unrelated to
  the app itself — a stale-widget-ID `KeyError` after any rerun that
  follows submitting a `type="password"` field), then `nav_radio.set_value(...).run()`
  through every screen option, asserting `at.exception` is empty. Always
  run this against a `/tmp` copy of `data/tutorai.db`, never the real one.

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
- Classes were first modeled as one homeroom per grade (a pure grouping,
  unrelated to subjects/teachers). The user then asked to "connect each
  student to various classes" with "teachers teaching 3-5 classes each,"
  which doesn't fit a one-per-grade model — clarified via question, then
  split into two concepts: `classes.py` (teacher+grade+subject, what
  students connect to several of) and `homerooms.py` (the original
  grade-homeroom idea, kept as a *separate* concept per the user's
  follow-up: "there is also one common homeroom per a certain amount of
  students per grade"). The old `classes` table's data wasn't thrown
  away — `db.py`'s migration renames it straight into `homerooms` since
  the shape matched exactly.
- Teachers teach 3-5 classes, students connect to 2-4 (`seed_test_data.py`
  has one-off top-up passes — `top_up_teacher_assignments` /
  `top_up_student_links` — so accounts seeded under the old, lower
  ranges still end up in the new ones after a re-run).
- Ollama errors now distinguish "not installed" from "installed but not
  running," pointing to https://ollama.com/download only in the former
  case (`chat.is_ollama_installed()` / `tutor.is_ollama_installed()`),
  since a student with no Ollama at all needs different instructions
  than one who just hasn't run `ollama serve` yet.
- Logos (teacher test-drafting chatbot) reuses `chat_storage.py` as-is
  for its conversations -- same `chats`/`chat_messages` tables as
  Socrates, just owned by a teacher's username instead of a student's,
  since the schema never assumed a role. `chat.py`'s Ollama-call plumbing
  was factored into a shared `_call_ollama_chat` helper so `ask_assistant`
  doesn't duplicate `ask_tutor`'s request/response handling -- it just
  skips the RAG step entirely, per the earlier explicit instruction not
  to add RAG for teachers/admin yet.
- Artemis was originally just a display name (`config.ASSISTANT_NAMES`)
  with no chat behind it -- the user clarified all three names are
  meant to be actual AI assistants, so Artemis got the same base chat
  architecture as Logos (`chat.ask_assistant`, no RAG), renamed from
  `ask_logos` since the function was already role-agnostic. Unlike
  Socrates/Logos, Artemis isn't tied to a grade+subject (admin manages
  the whole platform, not one class), so it gets exactly one persistent
  chat instead of a switchable list.
- Logos's "analyze student struggles" mode is a second system prompt
  (`build_logos_analysis_prompt`), not a tool-calling agent -- the
  linked students' chat transcripts for that class are gathered once at
  chat-creation time (`build_class_activity_summary` in `app.py`,
  capped at `MAX_ACTIVITY_SUMMARY_LENGTH` chars as a simple context-
  window guard) and baked directly into the system prompt, then Logos
  is immediately asked an auto-sent opening question so the teacher sees
  a result without having to prompt it first.
- Teacher-uploaded exam material is RAG, but deliberately kept in its
  own chromaDB collection rather than the shared student one -- the
  earlier "no RAG for teachers yet" deferral was about not mixing this
  in carelessly, not about avoiding RAG forever.
- `chats.mode` ("draft"/"analyze", NULL for non-Logos chats) was added
  after the user pointed out that "analyze" chats should rely only on
  the baked-in student activity summary, never mix in a teacher's
  exam-material RAG context -- initially both Logos modes shared
  `ask_logos_with_material` for ongoing messages on the assumption that
  an empty/irrelevant retrieval is harmless, but that still meant
  drafting material could surface mid-analysis. Now ongoing messages
  check `chat["mode"]` and only "draft" (or legacy chats predating this
  column) get the RAG-enabled path.
- Moved all modules from flat root-level files into a `tutorai/` package
  plus a `tests/` directory with `pytest` coverage (user's explicit
  choice, 2026-06-20, overriding `AGENTS.md`'s earlier "keep it flat, no
  package structure" guidance — `AGENTS.md` has been updated to match).
  Entry-point scripts are now run as `python3 -m tutorai.<name>`, and the
  Streamlit app as `python -m streamlit run tutorai/app.py`, instead of
  as bare scripts, so the package's absolute imports resolve.
- `chat.generate_structured_test` sends its prompt as a `role: "user"`
  message, not `role: "system"` with no user turn at all -- discovered
  by manual testing that Mistral via Ollama completely ignores format
  instructions in a system-only conversation and emits unrelated
  training-data-like snippets instead (e.g. random algebra word
  problems), even though the *exact same text* sent as a user message
  reliably produces well-formatted output. `ask_assistant` and
  `ask_logos_with_material` were unaffected since they always have at
  least one prior user turn in the conversation by the time they're
  called.
- Structured tests are multiple-choice only and one-shot generated (not
  part of the open-ended Logos chat above), per the user's choice, since
  a strict parseable format is much more reliable to get from a small
  local model as a single dedicated call than as part of free-flowing
  conversation. `exams.parse_structured_test` is deliberately tolerant
  (returns whatever it can parse rather than raising) since the model
  still occasionally undershoots the requested question count.
- Flashcards are generated deterministically (question text + the
  correct option's text), not via another LLM call -- per the user's
  ask, and also because the machine running this (8GB RAM, no dedicated
  GPU) is already tight on resources for one local model at a time; see
  the performance note below.

## Known gotcha: hardware constraints on local generation

This machine has 8GB RAM and no dedicated GPU (Apple M2, unified
memory). Running Mistral (~5.3GB loaded) is already a significant
fraction of that, so layering on a second model concurrently is
expensive. `rag.retrieve_relevant_chunks` now checks
`vector_store._collection.count()` and returns `[]` immediately if a
collection is empty, skipping the embedding model load entirely instead
of paying for it on every call when there's nothing to search (this cut
`generate_structured_test`'s time from ~56s to ~47s on this machine when
no exam material had been uploaded). Generating a multiple-choice test
still reliably takes 30-60+ seconds even after that fix -- this is
inherent to running a 7B model on this hardware, not a code bug. If
generation feels like it's hanging, it's very likely still running
rather than stuck; `ollama ps` can confirm a model is actively loaded.

## Known gotcha (db.py / users.py / chat_storage.py)

`data/tutorai.db` is gitignored since it contains password hashes,
encrypted passwords, and private chat content — don't remove it from
`.gitignore`. There is no migration script from the old JSON format; the
JSON files were deleted during the SQLite migration since no real user
data existed yet.

## Security note: admin can view passwords (deliberate tradeoff)

`crypto.py` encrypts every password with `cryptography`'s Fernet
(symmetric, authenticated encryption) using a key stored at
`data/secret.key` (gitignored, generated on first use). `users.get_plaintext_password`
decrypts it for the admin dashboard's "view password" field.

This was the user's explicit choice after being warned: I first
recommended keeping passwords hash-only and using the existing
password-reset button instead, since reversible encryption means
anyone who gets `data/secret.key` *and* the database can recover every
real student's and teacher's actual password — not just test accounts.
The user chose "store passwords reversibly for everyone" anyway. Login
verification itself still uses the one-way PBKDF2 hash and is
unaffected; only the new admin-facing feature carries this risk.

Practical implications to keep in mind:
- `data/secret.key` must never be committed or shared — treat it like a
  master password.
- Accounts created before this feature existed (or whose password was
  never reset since) have `encrypted_password = NULL` and show "not
  available" in the admin view until their password is reset.
- Test accounts (`seed_test_data.py`) intentionally use a simple shared
  password (`"1234"`, in `PASSWORD`) since they're "just to test out"
  per the user — every run resets all test accounts back to it via
  `reset_test_passwords`, even ones seeded under an older, more complex
  test password.

## Not yet built

- Per-chat model selection (currently one global model for all chats).
- Deleting/renaming chats (test chats included). (Unlinking a student
  from a teacher is now built — admin's Students menu has a remove
  button per link.)
- RAG for Artemis (admin) — explicitly deferred by the user; Logos
  (teacher) got it once the user asked for exam-material upload, but
  Artemis still has none.
- Multiple-choice only for published/auto-graded tests (per the user's
  choice) — Logos's freeform "Draft a test" mode can still produce mixed
  question types (short answer, open-ended), but those stay
  print-only via `exams.save_test`, not completable in the app.
- No per-question review for teachers — the published-tests list shows
  each student's total score, not which specific questions they missed.
- No way to un-publish a test or let a student retake one — one
  attempt per student per test, enforced at the DB level
  (`test_submissions` UNIQUE constraint), with no override path yet.
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
