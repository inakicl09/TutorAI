"""Entry point for the PUBLIC TEST site on Streamlit Community Cloud.

Identical to streamlit_app.py. It exists only because Community Cloud
won't create a second app from the same repo + branch + main file: when
asked to, it just opens the existing app (the full demo) instead. The
test site deploys from this file, and its Secrets (TUTORAI_PUBLIC_TEST =
"1", etc., see README) are what make it the limited version.
"""

import runpy

runpy.run_module("tutorai.app", run_name="__main__")
