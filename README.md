# TutorAI

See `CLAUDE.md` for the full project rundown and `AGENTS.md` for coding
conventions.

## Running

```
./run.sh
```

The first run creates `.venv` and installs `requirements.txt`, then
starts the Streamlit app (`tutorai/app.py`). Requires `ollama serve`
running locally.

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
isn't covered since it needs a real Ollama embedding model running.