# TutorAI

There are two hosted copies: the **full demo** (everything, including a
"log in as any user" shortcut) and the **public test site** (sign-up only,
for testers). See below.

See `CLAUDE.md` for the full project rundown and `AGENTS.md` for coding
conventions.

## Online version (nothing to install)

TutorAI is hosted on Streamlit Community Cloud, so anyone can open it in a
browser from a link. Every fresh start comes with demo data: an admin, 10
teachers and 120 students, each student with chats about their own
subjects. Every demo account's password is `1234`, and the "log in as any
user" dropdown under the login form jumps straight into any account.

The demo resets itself: after about 12 hours without visitors the app goes
to sleep, and the next visitor clicks "wake up" and gets fresh demo data.

### Publishing it (one-time setup)

1. Go to https://share.streamlit.io and sign in with GitHub, allowing
   access to private repositories.
2. **Create app** → repository `inakicl09/TutorAI`, branch `main`, main
   file `streamlit_app.py`.
3. **Advanced settings** → Python version **3.11**, and in **Secrets** put:
   ```
   GROQ_API_KEY = "gsk_...your key..."
   ```
4. **Deploy**. The first build takes a few minutes.
5. In the app's **Settings → Sharing**, make it public and copy the link.

Every push to `main` redeploys the app automatically.

## Public test site (the link you send to testers)

A second copy of the same app, made for strangers to try. It differs from
the full demo above only because its Secrets contain
`TUTORAI_PUBLIC_TEST = "1"`:

- No "log in as any user" box. The page opens on **Crear cuenta**, for
  students only.
- When signing up, a student picks their grade and 2 or 3 of its subjects.
  They are linked automatically to `profesor_tutorai`, a teacher who
  teaches every subject in every grade.
- There are no fake demo accounts. "Vincular profesor" and "Material" are
  hidden.
- A "📝 Danos tu opinión" button links to your Google Form.
- Accounts and chats are **kept**: the database is backed up to Supabase
  Storage (free) and restored when the app restarts.
- When Groq's free limit is hit, it switches to the other free model, and
  only if both are busy does it ask the tester to wait a minute.

Everything is on free plans. Never enter a card anywhere, and don't
upgrade anything. Both sites update on every push to `main`. The full demo
behaves exactly as before.

### Setting it up (about 15 minutes, all free)

You need the secrets text Claude prepared for you. It already contains the
Groq key, the switch, an encryption key and two passwords. You fill in the
three remaining lines.

**A. Supabase: where accounts get saved**

1. Go to https://supabase.com → **Start your project** → sign in with
   GitHub.
2. **New project**. Name `tutorai`, any database password (you won't need
   it), region **West EU (Ireland)**. Then **Create new project**, and wait
   about a minute. If it asks for a plan, choose **Free**.
3. Left sidebar → **Storage** → **New bucket**. Name it exactly
   `tutorai-backups`, leave **Public bucket** OFF, then **Create**.
4. Left sidebar → **Project Settings** (gear icon):
   - **Data API** (or the project's home page): copy the **Project URL**,
     e.g. `https://abcd1234.supabase.co`. Paste it inside the quotes of
     `SUPABASE_URL`.
   - **API Keys**: copy the **secret** key (starts with `sb_secret_`).
     If you only see "Legacy API keys", copy the **service_role** key
     instead. Paste it inside the quotes of `SUPABASE_SERVICE_KEY`.
     This key is secret. It only ever goes in Streamlit's Secrets box.

**B. Google Form link**

In your form: **Send** → 🔗 tab → tick **Shorten URL** → **Copy**. Paste it
inside the quotes of `FEEDBACK_FORM_URL`. Tip: add a question "¿Cuál es tu
nombre de usuario en TutorAI?" so you can match each answer to that
person's chats.

**C. Streamlit: create the second app (the new link)**

1. https://share.streamlit.io → **Create app** → **Deploy a public app
   from GitHub**.
2. Repository `inakicl09/TutorAI`, branch `main`, main file
   **`streamlit_app_prueba.py`**. It has to be this file, not
   `streamlit_app.py`: Cloud won't create two apps from the same file and
   just opens the existing full demo instead. Under **App URL**, type a new name, e.g.
   `socratictutordemo-prueba`. That gives
   `https://socratictutordemo-prueba.streamlit.app`.
3. **Advanced settings** → Python **3.11** → paste the whole completed
   secrets text into **Secrets** → **Save**.
4. **Deploy** and wait about 5 minutes.
5. Check it: you should see "Crear cuenta" with Curso + asignaturas, and
   **no** "Entrar como este usuario" box. Then **⋮ → Settings → Sharing**:
   make sure it is public. That link is the one you send.

Your existing app is not touched and keeps its link and full demo.

**D. Watching the test**

Log in on the test site with the passwords from the secrets text:
- `profesor_tutorai` → *Supervisar alumnos*: every tester's chats. You can
  also publish tests or announcements to testers here.
- `admin` → *Alumnos* and *Reportes de errores*. Its main menu also says
  whether the Supabase backup is working.

**Good to know**

- Supabase pauses free projects after 7 days with no activity and emails
  you. Click **Restore project** in Supabase. While it's paused, the app
  still opens but saves nothing, and the admin main menu shows a warning.
  Your saved data is never overwritten.
- If the app is shut down abruptly, the last ~15 seconds of activity can
  be lost. Everything older is in the backup, and Supabase also keeps
  hourly copies in `snapshots/`.

## Running it on your own computer

```
./run.sh
```

The first run creates `.venv` and installs `requirements.txt`, then
starts the app and prints a local link to open. It needs a `.env` file in
this folder with your Groq key (get one free at https://console.groq.com):

```
GROQ_API_KEY=gsk_...your key...
```

Other entry points (run from the repo root, with `.venv` activated):

```
python3 -m tutorai.tutor            # command-line prototype
python3 -m tutorai.create_admin     # one-time admin account setup
python3 -m tutorai.seed_test_data   # seed sample teachers/students
```

## Testing

```
pip install -r requirements-dev.txt
pytest
```

Tests live in `tests/` and use a temporary SQLite database (see
`tests/conftest.py`), so they never touch `data/tutorai.db`. `rag.py`
isn't covered since it needs the real local embedding model.
