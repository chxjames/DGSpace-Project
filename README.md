# DGSpace — 3D Print Request Management System

A web application for Donald's Garage that lets students submit 3D print requests and admins review and manage them.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Django 5.2 (template rendering, port 8000) |
| Backend API | Python Flask 3.0 (REST API, port 5000) |
| Database | MySQL 8.0 (local) |
| Auth | JWT tokens + bcrypt + Email verification |
| Python env | virtualenv at `.venv/` |

---

## Project Structure

```
DGSpace-Project-1/
├── start.ps1                  # <- Start both servers (run this!)
├── .venv/                     # Shared Python virtual environment
├── backend/                   # Flask REST API (port 5000)
│   ├── app.py                 # All API routes
│   ├── auth_service.py        # Register / login / JWT logic
│   ├── email_service.py       # Email verification (Gmail SMTP)
│   ├── print_service.py       # Print request logic
│   ├── totp_service.py        # 2FA - dormant, not yet in UI
│   ├── database.py            # MySQL connection wrapper
│   ├── config.py              # Loads settings from .env
│   ├── .env                   # Local secrets (not committed)
│   └── requirements.txt       # Python dependencies
├── frontend/                  # Django frontend (port 8000)
│   ├── manage.py
│   ├── donaldsgarage/         # Django project settings & URLs
│   ├── accounts/              # Views, URL routing, API proxy
│   └── templates/             # HTML pages
│       ├── base.html          # Layout, CSS, JS helpers
│       ├── home.html          # Landing / dashboard
│       ├── print_requests.html
│       ├── print_request_new.html
│       ├── print_request_detail.html  # Detail + Three.js STL viewer
│       └── registration/
│           ├── login.html
│           └── signup.html
└── database/
    ├── schema.sql             # Full DB schema (7 tables)
    ├── migration_001_print_requests.sql
    └── migration_002_stl_upload.sql   # Adds stl_file_path, stl_original_name
```

---

## How to Start

### Every session

**Option A** — right-click `start.ps1` → Run with PowerShell

**Option B** — PowerShell terminal:

```powershell
# Stop any old Python processes first
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Start both servers
powershell -ExecutionPolicy Bypass -File e:\DGSpace-Project-1\start.ps1
```

This opens **two PowerShell windows**:

- Flask backend → `http://localhost:5000` (keep open — shows verification codes)
- Django frontend → `http://localhost:8000`

Then open **`http://localhost:8000`** in your browser.

> **Note:** Do NOT use the VS Code Simple Browser — it blocks some requests.

---

## Architecture

```
Browser
  |
  | HTTP to localhost:8000
  v
Django (port 8000)
  |- Serves HTML templates
  |- /api/* --> proxied to Flask (ApiProxyView, csrf_exempt)
                    |
                    v
                Flask (port 5000)
                    |- REST API
                    v
                 MySQL (DGSpace)
```

All browser JS uses relative URLs (`/api/...`) — everything routes through Django, no CORS issues.

---

## Pages

| URL | Description |
| --- | --- |
| `/` | Home / dashboard |
| `/accounts/login/` | Log in |
| `/accounts/signup/` | Sign up |
| `/print-requests/` | My print requests |
| `/print-requests/new/` | Submit new request |
| `/print-requests/<id>/` | Request detail + Three.js STL preview |
| `/print-requests/<id>/return/` | Admin: send feedback to student (writes `admin_notes` and sets status to `pending`) |
| `/admin/students/` | Admin-only student accounts list + delete |

---

## API Endpoints

### Students

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/api/students/register` | Register (triggers email verification) |
| POST | `/api/students/verify-email` | Submit 6-digit code |
| POST | `/api/students/resend-verification` | Resend code |
| POST | `/api/students/login` | Login, returns JWT |

### Admins

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/api/admins/register` | Register admin |
| POST | `/api/admins/verify-email` | Verify admin email |
| POST | `/api/admins/login` | Login, returns JWT |
| GET | `/api/admin/students` | List all student accounts |
| DELETE | `/api/admin/students/<email>` | Delete a student account (also deletes their print requests) |

### Print Requests

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/print-requests/my-requests` | Student: list own requests |
| POST | `/api/print-requests` | Student: submit new request (includes optional STL info) |
| POST | `/api/print-requests/upload-stl` | Student: upload `.stl` file, returns `filename` |
| GET | `/api/print-requests/<id>` | Get single request details (includes `stl_file_path`) |
| DELETE | `/api/print-requests/<id>` | Student: delete own **pending** request (also deletes uploaded STL file from `backend/uploads/` when present) |
| GET | `/api/uploads/<filename>` | Serve uploaded STL files |
| GET | `/api/admin/print-requests` | Admin: list all requests |
| POST | `/api/admin/print-requests/<id>/return` | Admin: send feedback to student (stores message in `admin_notes`, status set to `pending`) |

---

## First-Time Setup

### 1. Database

```powershell
$mysql = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
& $mysql -u root -p DGSpace < database/schema.sql
& $mysql -u root -p DGSpace < database/migration_001_print_requests.sql
& $mysql -u root -p DGSpace < database/migration_002_stl_upload.sql
```

Tables: `students`, `admins`, `email_verification_codes`, `password_reset_tokens`, `totp_secrets`, `print_requests`, `print_request_history`

### 2. Python environment

```powershell
python -m venv .venv
.venv\Scripts\pip install -r backend/requirements.txt
.venv\Scripts\pip install django requests
```

### 3. Create `backend/.env`

```properties
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=dgspace_user
DB_PASSWORD=password
DB_NAME=DGSpace

JWT_SECRET_KEY=dgspace-super-secret-2026-change-in-production

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

FLASK_ENV=development
PORT=5000

# Set to True to print verification codes to terminal instead of emailing
DEV_EMAIL_MODE=True
```

---

## Email Verification

**Dev mode** (`DEV_EMAIL_MODE=True`):

- No real email is sent
- Code appears in the **Flask terminal window**:

```text
[DEV] Verification code for user@email.com: 483921
```

- Or query the database:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root "-ppassword" DGSpace -e "SELECT email, verification_code, expires_at FROM email_verification_codes ORDER BY created_at DESC LIMIT 5;"
```

**Production mode** (`DEV_EMAIL_MODE=False`):

1. Google Account → Security → **App Passwords** → generate 16-char password
2. Fill in `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER` in `.env`
3. Set `DEV_EMAIL_MODE=False` and restart Flask

---

## Reset a Password (Dev)

Use Python — never use PowerShell mysql with `$` in the value (escaping corrupts bcrypt hashes):

```python
import bcrypt, mysql.connector
conn = mysql.connector.connect(host="127.0.0.1", user="root", password="password", database="DGSpace")
cursor = conn.cursor()
new_hash = bcrypt.hashpw(b"yournewpassword", bcrypt.gensalt()).decode()
cursor.execute("UPDATE students SET password_hash=%s WHERE email=%s", (new_hash, "user@email.com"))
# For admin accounts use: UPDATE admins SET password_hash=...
conn.commit()
print("Done")
```

---

## Security Notes

- Never commit `.env` (add it to `.gitignore`)
- JWT tokens stored in browser `localStorage` (`dg_token`, `dg_user`)
- Token expiry: 24 hours
- Verification codes expire in 15 minutes
- Passwords hashed with bcrypt (12 rounds)
- TOTP 2FA is implemented in `totp_service.py` but not yet exposed in the UI
