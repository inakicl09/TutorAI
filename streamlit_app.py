"""Entry point for hosting TutorAI on Streamlit Community Cloud.

Cloud starts the app with the bare `streamlit run <file>` command, which
only puts that file's own folder on sys.path. Running tutorai/app.py
directly that way breaks every `from tutorai import ...` line (that's why
run.sh uses `python -m streamlit` instead). Living at the repo root, this
file puts the repo root on sys.path, so the tutorai package imports fine.

run_module (not a plain `import tutorai.app`) matters: Streamlit re-runs
this script on every click, and a normal import would only execute
app.py the first time.
"""

import runpy

runpy.run_module("tutorai.app", run_name="__main__")
