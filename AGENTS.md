# Instructions for coding agents

1. Read `README.md` first. Keep Vision Lab small and understandable: prefer short, direct code; add dependencies, files or abstractions only when a current feature needs them.
2. Build only what is asked. Explain choices in plain language for a non-specialist owner.
3. Keep the pipeline separate from the UI: source → rolling cache → derived streams → analysis. `app.py` only displays and controls.
4. Timing is sacred: use the file's presentation timestamps, never a nominal frame rate. The camera and analysis must never see frames that have not arrived yet.
5. Never modify, overwrite or delete users' original videos, or existing files in `data/` or `runs/`. Do not commit videos, model weights or secrets.
6. Add or update tests for behaviour you change, and run `python -m pytest -q`. Start the app with `python start.py`. Report honestly what was and was not verified (for example real Codespaces or real phone footage).
7. Finish with a summary of changes, testing, limitations and suggested next steps.
