#!/usr/bin/env bash
# Starts TutorAI. Creates the virtual environment and installs
# dependencies the first time it's run, then just activates it.
set -e

cd "$(dirname "$0")"

# Find Python 3.9 or newer. The system python3 on older Macs is 3.7,
# which is too old for the app's dependencies. Download a newer Python
# from https://www.python.org/downloads/ if none is found below.
PYTHON=""
for candidate in python3.12 python3.11 python3.10 python3.9 python3.13 python3.14; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

# Some systems (e.g. Apple's Command Line Tools python3) only expose a
# bare "python3", no versioned name -- fall back to it, but check its
# actual version since on older Macs "python3" alone can still be 3.7.
if [ -z "$PYTHON" ] && command -v python3 &>/dev/null; then
    if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
        PYTHON="python3"
    fi
fi

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.9 or newer is required."
    echo "Download it from https://www.python.org/downloads/ and try again."
    exit 1
fi

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment with $PYTHON..."
    "$PYTHON" -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    echo "Installing dependencies..."
    pip install --prefer-binary -r requirements.txt
else
    source "$VENV_DIR/bin/activate"
fi

# Load .env so the GROQ_API_KEY is available to the app.
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# --server.headless skips Streamlit's first-run "enter your email" prompt,
# which otherwise blocks silently when run from a script instead of a TTY.
# Using "python -m streamlit" (not the bare "streamlit" command) adds this
# directory to sys.path, which is what lets tutorai/app.py import the rest
# of the tutorai package with "from tutorai import ...".
python -m streamlit run tutorai/app.py --server.headless true
