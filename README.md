# Penguin Coding School Dashboard

A Django-based student/teacher dashboard for managing classes, assignments, and code submissions. Features an in-browser Python code editor powered by Pyodide/WebAssembly, allowing students to write and run Python code — including turtle graphics and pygame — entirely in their browser.

## Tech Stack

- **Backend**: Django 5.2.5 (Python web framework)
- **Database**: PostgreSQL (required for development and production)
- **Frontend**: HTML/CSS/JavaScript with a Pyodide-based Python editor
- **Code Runtime**: Pyodide/WebAssembly (client-side Python interpreter running in Web Workers)
- **Storage**: File system for development, AWS S3 for production
- **Additional Libraries**:
  - `django-storages` — S3 integration
  - `django-debug-toolbar` — dev debugging tools
  - `psycopg` — PostgreSQL driver
  - `python-dotenv` — environment variable management

## Prerequisites
- **Python 3.11+** (check with `python --version`)
- **PostgreSQL 12+** installed and running locally
- **pip** (usually included with Python)

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd pythonhomeworkdashboard
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

Create a `.env` file in the project root. **Note**: The database credentials below are values you'll create on your own machine in Step 5 — they don't come from anywhere else.

```env
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_SETTINGS_MODULE=mysite.settings.dev

# Database (you'll create these yourself in Step 5)
DB_NAME=penguin_dashboard_dev
DB_USERNAME=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432

# S3 (keep as false for development)
USE_S3=false
```

**Secret Key Generation**: Generate a secure secret key using Python:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5. Set Up PostgreSQL

This is where you create the database and user that you'll reference in your `.env` file:

```bash
# Start PostgreSQL (if not already running)
# macOS with Homebrew:
brew services start postgresql

# Create the development database (matches DB_NAME in .env)
createdb penguin_dashboard_dev

# PostgreSQL comes with a default 'postgres' user
# You can use that, or create a new one:
createuser -P myusername  # You'll be prompted for a password
```

Then update your `.env` file with:
- `DB_NAME=penguin_dashboard_dev` (the database you just created - you can pick a different name)
- `DB_USERNAME=postgres` (or whatever user you created/chose above)
- `DB_PASSWORD=` (the password you just set)
- `DB_HOST=localhost` (always localhost for local dev)
- `DB_PORT=5432` (PostgreSQL default)

### 6. Run Migrations

```bash
export DJANGO_SETTINGS_MODULE=mysite.settings.dev
python manage.py migrate
```

### 7. Create a Superuser (Admin Account)

```bash
export DJANGO_SETTINGS_MODULE=mysite.settings.dev
python manage.py createsuperuser
```

Follow the prompts to create your admin user.

### 8. Start the Development Server

```bash
export DJANGO_SETTINGS_MODULE=mysite.settings.dev
python manage.py runserver
```

The app should now be running at `http://localhost:8000`.

**Note**: The `DJANGO_SETTINGS_MODULE` export is required because `manage.py` defaults to production settings. You can add it to your shell profile (`.bashrc`, `.zshrc`) to avoid typing it each time:

```bash
# Add to ~/.zshrc or ~/.bashrc
export DJANGO_SETTINGS_MODULE=mysite.settings.dev
```

## Environment Variables

| Variable | Purpose | Example | You create this? |
|----------|---------|---------|---------|
| `DJANGO_SECRET_KEY` | Django's secret key for session signing and security | (generate with Python) | ✅ Yes, run the command in Step 4 |
| `DJANGO_SETTINGS_MODULE` | Which settings file to use (dev/prod) | `mysite.settings.dev` | ❌ Always this for dev |
| `DB_NAME` | PostgreSQL database name you create | `penguin_dashboard_dev` | ✅ Yes, create in Step 5 with `createdb` |
| `DB_USERNAME` | PostgreSQL user (usually the default) | `postgres` | ✅ Use default or create in Step 5 |
| `DB_PASSWORD` | Password for the PostgreSQL user | (you choose) | ✅ Yes, you set this |
| `DB_HOST` | Database host (localhost for dev) | `localhost` | ❌ Always localhost for dev |
| `DB_PORT` | Database port (PostgreSQL default) | `5432` | ❌ Always 5432 for PostgreSQL |
| `USE_S3` | Enable AWS S3 storage (dev should be `false`) | `false` | ❌ Always false for dev |

## Project Structure

```
pythonhomeworkdashboard/
├── dashboard/              # Main Django app
│   ├── models.py          # Data models (Class, Assignment, CodeProject, etc.)
│   ├── views.py           # View logic (editor, dashboards, APIs)
│   ├── urls.py            # URL routing
│   ├── static/editor/     # Client-side code editor
│   │   ├── main.js        # Editor UI and orchestration
│   │   ├── worker.js      # Python runtime (Pyodide) in Web Worker
│   │   └── turtle.js      # Turtle graphics implementation
│   └── templates/         # HTML templates
├── mysite/                # Django project configuration
│   ├── settings/
│   │   ├── base.py       # Shared settings
│   │   ├── dev.py        # Development settings
│   │   └── prod.py       # Production settings
│   ├── urls.py           # Root URL configuration
│   └── wsgi.py           # WSGI app entry point
├── manage.py             # Django management CLI
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (not in Git)
├── .gitignore           # Git ignore rules
└── CLAUDE.md            # Developer notes for Claude Code

```

## Understanding the Architecture

### Two Runtime Halves

1. **Django Backend** (`dashboard/`)
   - Handles authentication and authorization
   - Manages data (classes, assignments, submissions, code projects)
   - Provides REST-ish JSON APIs for the editor (autosave, file management)
   - No code execution on the server

2. **Client-Side Python Runtime** (`dashboard/static/editor/`)
   - Pyodide-based in-browser Python interpreter
   - Runs in a Web Worker (`worker.js`) — doesn't block UI
   - `main.js` handles the editor UI and orchestration
   - `turtle.js` implements turtle graphics - not currently used
   - Student code executes entirely in the browser via WebAssembly

### Key Data Models
- **User + Teacher/Student**: Users have a role (teacher or student) via OneToOneField profile models
- **Class**: Belongs to a teacher, has a unique join code for enrollment
- **Assignment**: Belongs to a teacher and curriculum, assigned to specific classes
- **CodeProject**: A unit of student work (one per student per assignment per class)
- **ProjectFile**: One file within a CodeProject (supports multi-file projects)

### Access Control
- No Django permission groups — role is derived structurally (`hasattr(user, "student")` or `hasattr(user, "teacher")`)
- `@student_required` and `@teacher_required` decorators redirect to appropriate dashboards
- `Teacher.is_admin` gates admin-only views
- View-level ownership checks are manual (not object-level permissions)