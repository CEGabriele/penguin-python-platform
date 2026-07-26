# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Django app for Penguin Coding School: a student/teacher dashboard for managing classes, assignments, and submissions, built around an in-browser Python code editor (Pyodide/WASM) so students can write and run Python — including turtle graphics and pygame — entirely client-side.

## Commands

Settings are split into `mysite/settings/{base,dev,prod}.py`. **`manage.py` defaults to `mysite.settings.prod`**, so local work must explicitly select dev settings:

```bash
export DJANGO_SETTINGS_MODULE=mysite.settings.dev
python manage.py runserver
python manage.py migrate
python manage.py test dashboard          # run app tests
python manage.py test dashboard.tests.SomeTestCase.test_method  # single test
python manage.py createsuperuser
```

Dependencies are pinned in `requirements.txt` (no Pipfile/poetry). A `.env` file (loaded via `python-dotenv`) holds DB, AWS/S3, Azure OpenAI, and Django secret settings — see `mysite/settings/base.py` for the full list of expected keys.

There is currently no meaningful test suite (`dashboard/tests.py` is the default stub) and no linter/formatter configured — don't assume `ruff`/`black`/`flake8` conventions are enforced.

## Architecture

### Two runtime halves

1. **Django backend** (`dashboard/`) — auth, class/assignment/submission data model, and a REST-ish JSON API for the code editor (autosave, file CRUD).
2. **Client-side Python runtime** (`dashboard/static/editor/`) — a Pyodide-based in-browser Python interpreter running in a Web Worker (`worker.js`), with `main.js` (editor UI/orchestration) and `turtle.js` (canvas-based turtle graphics shim). Code never executes on the server — it runs in the student's browser via WebAssembly.

### Roles and access control

There's no Django group/permission framework in use — role is derived structurally:
- `Teacher` and `Student` are both `OneToOneField(User)` profile models (`dashboard/models.py`). `get_user_role(user)` / `hasattr(user, "student"|"teacher")` is the idiom used everywhere (views, decorators) to branch behavior — there is no `role` field to check.
- `@student_required` / `@teacher_required` decorators in `dashboard/views.py` redirect to the other dashboard if the role doesn't match, rather than 403ing.
- `Teacher.is_admin` gates the admin-only views (`admin_dashboard`, `admin_class_view`); this is separate from Django's `is_staff`/superuser.
- View-level ownership checks are manual (e.g. `editor_view` checks `project.owner != request.user` or that a teacher owns the project's class) — there's no object-level permissions library.

### Core data model relationships

- `Class` belongs to one `Teacher`, optionally has a `Curriculum`, and has a unique join `code` (auto-generated in `save()`) students use to enroll.
- `Assignment` belongs to a `Curriculum` and a `Teacher`; it's attached to specific classes via `AssignedToClass` (with its own `due_date`), not directly.
- `CodeProject` is the unit of student work: owned by a `User`, optionally tied to a `Class` and an `Assignment`. The `(owner, for_class, assignment)` triple is unique — one project per student per assignment per class.
- `ProjectFile` is one file within a `CodeProject` (path + FileField), unique per `(project, path)`. Multi-file projects are supported — `main.py` is the conventional entry point (see `ensure_main_file` in `views.py`).
- Several free functions in `models.py` (`unique_student_upload_path`, `upload_path`) are dead code kept alive **only** because old migrations reference them by dotted path — removing them breaks `migrate --run-syncdb` replay on a fresh DB. Don't delete without also handling the historical migrations.

### Storage abstraction

`dashboard/storages.py` defines `StaticRootS3Boto3Storage` / `MediaRootS3Boto3Storage` / `PrivateMediaStorage`, each with **two implementations gated by `settings.USE_S3`**: real `S3Boto3Storage` subclasses when true, `FileSystemStorage` fallbacks when false. Always import these from `dashboard.storages`, not directly from `django-storages` or `django.core.files.storage`, so dev/prod parity holds. `prod.py` additionally sets Django's `STORAGES` dict for static/media; `dev.py` does not use S3.

### Editor request flow (`dashboard/views.py`)

`editor_view` is the single entry point for the code editor page and handles several distinct concerns behind one URL depending on query params / method:
- GET with `assigned_id` → resolves/creates the student's `CodeProject` for that assignment (`get_or_create_editor_project`, `ensure_main_file`) and loads `main.py`.
- GET with `project_id` (+ optional `file`) → loads a specific project/file directly, enforcing owner-or-teacher-of-class access.
- POST with JSON body → autosave: writes `code` to a `ProjectFile` at `path` for `project_id`, bumping `CodeProject.last_edited`.
- `project.submitted` flips the editor to read-only client-side (`is_readonly`).

The `editor/project/<id>/...` endpoints (rename/delete/move/create file, list files) are small JSON APIs consumed by `main.js`; teacher-facing file listing (`get_project_files_for_teacher`) is a separate read-only view with its own access check.

### Client-side Python execution (`dashboard/static/editor/worker.js`)

Runs entirely in a Web Worker, loading Pyodide from a CDN (no server round-trip to execute code):
- Injects a Python "bootstrap" (`PY_BOOTSTRAP`) that redirects `print`/`stdout` to `postMessage` and replaces `input()` with an async version that blocks on a JS `Future` resolved by an `input_response` message from the main thread — this is how the console UI provides interactive stdin.
- `autoWrapAsync()` statically rewrites submitted code: any function whose body (transitively) calls something requiring `await` gets turned into `async def`, and its call sites get `await` inserted. This lets synchronous-looking student code use blocking `input()` without them writing `async`/`await` themselves. Be careful modifying this — it's regex-based source rewriting, not an AST transform, so edits can be fragile around edge cases (e.g. it explicitly special-cases a bare `action()` call pattern for turtle/pygame event loops).
- `pygame-ce` is lazy-loaded via `pyodide.loadPackage` only when `usesPygame` is set. Turtle graphics is implemented separately in `turtle.js`, not via a Python package.
- Project files are synced into Pyodide's in-memory FS (`pyodide.FS.writeFile`) by diffing against `lastProjectFiles` before each run, so only changed files get rewritten.

### Settings layering

- `base.py` holds shared config and reads `.env` directly (defaults `DEBUG = True`, Postgres always, no S3 config).
- `dev.py` extends `base` with debug toolbar, console email backend, relaxed cookie/HSTS settings, and local file storage.
- `prod.py` extends `base` independently (re-imports `.base`, does **not** import `dev`) and turns on HSTS, secure cookies, SSL redirect, S3-backed `STORAGES`, and reads `DJANGO_ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` from env as comma-separated lists.
- `/healthz` and `/healthz/` (see `mysite/urls.py`, `dashboard.views.healthz`) check DB connectivity and are exempted from SSL redirect in prod (`SECURE_REDIRECT_EXEMPT`) — needed for load balancer health checks over plain HTTP.
