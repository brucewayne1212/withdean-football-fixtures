## Quick orientation for AI contributors

This repository is a Flask-based web app for managing football fixtures, generating emails, and tracking tasks. Use this file as the single-page cheat-sheet when making code changes.

Core components (read these files to understand the flow):
- `app.py` — Flask app, routes, Google OAuth (flask-dance), file uploads, CSV/coach import helpers, and session setup. This is the runtime entry for the web UI.
- `models.py` — SQLAlchemy models and `DatabaseManager`. Multi-tenant model: Organization -> Teams/Pitches/Fixtures/Tasks. Important constraints and JSONB fields live here.
- `main.py` — CLI runner that demonstrates how `FixtureParser` and `email_template.generate_email` are used to produce emails from spreadsheets.
- `task_manager.py` — legacy / lightweight task management using JSON files (supports `user_data/<user_id>/...`), used by some CLI/debug scripts and test harnesses.
- `fixture_parser.py`, `text_fixture_parser.py`, `email_template.py`, `smart_email_generator.py` — parsing and email generation logic. Inspect these when changing fixture/email behaviour.

Why the structure exists
- Multi-tenant: users own `Organization` records (see `User`, `Organization` in `models.py`). Most DB queries are scoped by `organization_id`.
- Two modes of task storage: persistent DB-backed `Task` model (preferred) and a JSON-based `TaskManager` for lightweight/local usage (see `TaskManager` in `task_manager.py`). Be careful when editing task logic; both systems must remain consistent where used.

Environment & local-run notes (critical)
- Required env vars: `SECRET_KEY` (≥32 chars), `DATABASE_URL`. Missing `SECRET_KEY` or `DATABASE_URL` will raise at startup (see `app.py`).
- OAuth: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` for Google sign-in. For local dev `OAUTHLIB_INSECURE_TRANSPORT=1` may be set by `app.py` when `FLASK_ENV=development` or `SERVER_NAME` contains `localhost`.
- Local run: `pip install -r requirements.txt` then `python app.py` (or `python main.py` for CLI email generation). The project expects Python 3.11 in docs.
- Deployment: Docker and Google Cloud Run configs are present (`Dockerfile`, `app.yaml`, `Procfile`). Cloud Run deploy in `README.md` shows `gcloud run deploy --source .` usage.

Testing and debugging
- Tests are mostly simple scripts (e.g., `test_new_logic.py`, `test_overall_status.py`, `test_parser_fix.py`) and are executed directly with `python test_new_logic.py`. They connect to a real Postgres DB by default — check the hard-coded `DATABASE_URL` inside those files before running.
- There is no pytest harness configured; treat test scripts as ad-hoc integration/debug helpers.

Important patterns & conventions
- Database access: use `DatabaseManager.get_session()` and always `session.close()` in `finally` blocks (most files follow this pattern). See `app.py` and `test_*` scripts.
- UUIDs: primary keys are PostgreSQL UUIDs (see `models.py`). The app validates UUID format before re-loading sessions in `load_user()`.
- Task status values and task types are constrained by DB check constraints. When adding new statuses/types update `models.py` constraints and any code that enumerates them (e.g., `task_manager.py`, dashboard logic in tests).
- Email templates: HTML templates are generated via `email_template.generate_email` and `generate_subject_line`. Templates are stored in DB (`EmailTemplate`), but default template is embedded in `app.py` as `get_default_email_template()` — keep edits in sync.
- File uploads: `app.config['UPLOAD_FOLDER']` is `uploads/`. Temporary bulk imports use OS temp via `tempfile.gettempdir()`; bulk files are stored with `user_id` prefixes (see `store_bulk_contacts`, `store_bulk_coaches`).

Integration points & external dependencies
- PostgreSQL (expects a `DATABASE_URL` compatible with SQLAlchemy). `models.DatabaseManager` creates engine with that URL.
- Google OAuth via `flask-dance` and standard Google APIs.
- Google Maps Static API is used in `app.py.generate_google_maps_url()` (requires `api_key` passed from settings/DB or env).
- Pandas/OpenPyXL used for spreadsheet parsing (`FixtureParser` uses `pandas`).

Concrete examples to copy-paste
- Open a DB session safely:
  ```py
  session = db_manager.get_session()
  try:
      # query or update
  finally:
      session.close()
  ```

- Create a task id (use same normalization logic as `TaskManager.create_task_from_fixture`): replace spaces, `/`, `:`, `.` with `_`.

Files to inspect first when making changes
- `app.py` (routes, auth, uploads)
- `models.py` (DB schema, constraints)
- `fixture_parser.py`, `text_fixture_parser.py` (parsing rules)
- `email_template.py`, `smart_email_generator.py` (message assembly)
- `task_manager.py` (legacy local task storage & JSON format)

What NOT to change without verification
- DB column names, check constraints, unique constraints in `models.py` without a migration plan.
- `SECRET_KEY` and `DATABASE_URL` handling in `app.py` (they intentionally raise if missing).
- OAuth initialization order (there's a comment that insecure transport must be set before importing OAuth libs).

If something is unclear
- Add a short unit or integration script in `tests/` or at repo root mirroring the pattern in `test_parser_fix.py` to reproduce behavior quickly.

Next step after edits
- Run `python -m pip install -r requirements.txt` (or use the project's virtualenv), then run `python app.py` for web, or the appropriate `test_*.py` script for focused checks. Update this file if you discover additional required dev commands.

If you want me to expand any section (deploy, DB migrations, tests) tell me which area to deep-dive into.
