#!/usr/bin/env bash
# Starts TutorAI. Creates the virtual environment and installs
# dependencies the first time it's run, then just activates it.
set -e

cd "$(dirname "$0")"

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    echo "Installing dependencies..."
    pip install -r requirements.txt
else
    source "$VENV_DIR/bin/activate"
fi

# --server.headless skips Streamlit's first-run "enter your email" prompt,
# which otherwise blocks silently when run from a script instead of a TTY.
# Using "python -m streamlit" (not the bare "streamlit" command) adds this
# directory to sys.path, which is what lets tutorai/app.py import the rest
# of the tutorai package with "from tutorai import ...".
python -m streamlit run tutorai/app.py --server.headless true
