# TutorAI

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
