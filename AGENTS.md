# AGENTS.md — TaskManager (Django)

Single Django 6.1 project. `tasks` is the only app. `taskmanager/` holds project
settings/urls. No monorepo, no backend/frontend split.

## Environment & running

- Virtualenv lives at repo root: `venv` (use `venv\Scripts\python` / `venv\Scripts\activate`).
- `run_server.bat` = `call venv\Scripts\activate.bat && python manage.py runserver 127.0.0.1:8000`.
- Settings module: `DJANGO_SETTINGS_MODULE=taskmanager.settings` (DEBUG=True).
- DB: `db.sqlite3` in repo root. **No default admin user** — create one with
  `python manage.py createsuperuser` before testing protected pages.
- Static: root `static/` + app-level; templates live in root `templates/`.
- `debug_stats.py` is a manual debug snippet (logs in as `admin`), not a test.

## Commands

- Run site: `python manage.py runserver 127.0.0.1:8000`
- Apply migrations: `python manage.py migrate`
- Make migrations (after model changes): `python manage.py makemigrations tasks`
- Admin: `python manage.py createsuperuser`
- Check config: `python manage.py check`
- Tests: `python manage.py test`  (stub — `tasks/tests.py` is empty)
- No lint/typecheck/pre-commit/CI configured in this repo.

## Auth & URLs

- Uses Django's default `User` model (no custom user model).
- Login/logout/password via `accounts/` (`django.contrib.auth.urls`); `LOGIN_URL='login'`.
- All `tasks.views` except `home` are `@login_required`; `/tasks/stats/` redirects to `/accounts/login/`.

## Gotchas worth knowing

- **Plotly load order (was a real bug):** `stats` view builds charts with
  `fig.to_html(include_plotlyjs=False)`, so each chart emits an inline
  `Plotly.newPlot(...)` script. Plotly.js **must** be loaded in `<head>`
  (via `{% block extrahead %}`). If you put `<script src="cdn.../plotly-latest.min.js">`
  at the end of `<body>`, the inline render scripts run first → `ReferenceError:
  Plotly is not defined` → the chart cards stay blank. Fix: load plotly in
  `extrahead`, never after the chart markup.
- `tasks/stats` reads tasks via `request.user.tasks.values(...)` and builds a
  pandas DataFrame; an empty DataFrame is handled (returns early, no charts).
- `Task.save()` auto-sets `completed_at=now()` when status flips to `DONE` and
  clears it otherwise — do not rely on the field being null for in-progress tasks.
- `Task.description` is rendered as HTML in templates; watch for XSS if user input allowed.
