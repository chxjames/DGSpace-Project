# DGSpace — 3D Print Request Management System

A full-stack web application for **Donald's Garage** that lets students submit 3D print requests and admins review, slice, and manage them through a streamlined workflow.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Django 5.2 (template rendering, port 8000) |
| Backend API | Python Flask 3.0 (REST API, port 5000) |
| Database | MySQL 8.0 (local) |
| Auth | JWT tokens + bcrypt + Email verification + TOTP 2FA |
| 3D Viewer | Three.js 0.165 (STL preview in browser) |
| UFP Parsing | Custom parser for Cura `.ufp` slice data |
| Reports | Google Sheets integration (weekly print logs) |
| Python env | virtualenv (`.venv/`) |

---

## Project Structure

```
DGSpace-Project-1/
├── start.ps1                  # Start both servers (run this!)
├── .venv/                     # Shared Python virtual environment
│
├── backend/                   # Flask REST API (port 5000)
│   ├── app.py                 # All API routes
│   ├── auth_service.py        # Register / login / JWT logic
│   ├── email_service.py       # Email verification (Gmail SMTP)
│   ├── print_service.py       # Print request CRUD
│   ├── totp_service.py        # 2FA (TOTP) — setup, verify, disable
│   ├── ufp_analysis.py        # Parse Cura .ufp files (print time, material, etc.)
│   ├── sheet_service.py       # Google Sheets API wrapper
│   ├── report_service.py      # Weekly/monthly report aggregation
│   ├── database.py            # MySQL connection wrapper
│   ├── config.py              # Loads settings from .env
│   ├── uploads/               # Uploaded STL & UFP files (UUID-named)
│   ├── .env                   # Local secrets (not committed)
│   └── requirements.txt       # Python dependencies
│
├── frontend/                  # Django frontend (port 8000)
│   ├── manage.py
│   ├── donaldsgarage/         # Django project settings & URL routing
│   ├── accounts/              # Views + API proxy to Flask
│   └── templates/
│       ├── base.html                  # Layout, CSS, shared JS helpers
│       ├── home.html                  # Landing / dashboard
│       ├── print_requests.html        # Request list (student & admin)
│       ├── print_request_new.html     # Student: submit new request
│       ├── print_request_detail.html  # Detail page + Three.js STL viewer + admin actions
│       ├── admin_students.html        # Admin: student management
│       ├── weekly_report.html         # Weekly print report
│       ├── report_sync.html           # Google Sheets sync UI
│       ├── report_raw.html            # Raw data view
│       └── registration/
│           ├── login.html
│           └── signup.html
│
└── database/
    ├── schema.sql             # Full database schema
    └── migration_*.sql        # Incremental migrations
```

---

## Architecture

```
Browser
  |
  | HTTP to localhost:8000
  v
Django (port 8000)
  |- Serves HTML templates
  |- /api/* --> proxied to Flask (ApiProxyView)
                    |
                    v
                Flask (port 5000)
                    |- REST API
                    v
                 MySQL (DGSpace)
```

All browser JS uses relative URLs (`/api/...`) — everything routes through Django, no CORS issues.

---

## Features

### Student Side

- **Register & Login** — Email verification required; optional TOTP 2FA
- **Submit Print Request** — Upload `.stl` file, choose material/color, set optional deadline
- **3D STL Preview** — Interactive Three.js viewer on the detail page (rotate, zoom)
- **Track Status** — See request status (Pending → Approved → In Progress → Completed)
- **Receive Feedback** — Admin feedback displayed with revision instructions

### Admin Side

- **Review Requests** — Unified review panel shown immediately on detail page:
  - Download STL → Slice in Cura → Upload `.ufp` → Approve
  - Or write feedback in notes → Send Back for revision
  - Or Reject outright
- **UFP Slice Data** — Auto-parsed from Cura `.ufp` files (print time, material weight, layer height, infill)
- **Student Management** — View/delete student accounts
- **Status Workflow** — `pending` → `approved` → `in_progress` → `completed` (or `rejected` / `cancelled`)
- **Reports Dashboard** — Weekly/monthly reports synced from Google Sheets

### Security

- JWT authentication with 24-hour token expiry
- Passwords hashed with bcrypt
- Email verification (6-digit code, 15-minute expiry)
- Optional TOTP 2FA (Google Authenticator compatible)
- File upload validation (type, size limits)

---

## Prerequisites

- **Python 3.10+**
- **MySQL 8.0+** (running locally)
- **Cura** (for slicing STL → UFP files, admin workflow)

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/chxjames/DGSpace-Project.git
cd DGSpace-Project
```

### 2. Create the virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend/requirements.txt
pip install django
```

### 3. Set up the database

```powershell
$mysql = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
& $mysql -u root -p DGSpace < database/schema.sql
& $mysql -u root -p DGSpace < database/migration_001_print_requests.sql
& $mysql -u root -p DGSpace < database/migration_002_stl_upload.sql
& $mysql -u root -p DGSpace < database/migration_003_revision_requested.sql
& $mysql -u root -p DGSpace < database/migration_005_ufp_fields.sql
& $mysql -u root -p DGSpace < database/migration_006_deadline.sql
```

Tables: `students`, `admins`, `email_verification_codes`, `password_reset_tokens`, `totp_secrets`, `print_requests`, `print_request_history`

### 4. Configure environment variables

Create `backend/.env`:

```ini
# Database
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=dgspace_user
DB_PASSWORD=your_password
DB_NAME=DGSpace

# JWT
JWT_SECRET_KEY=your_random_secret_key

# Email (Gmail SMTP)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_DEFAULT_SENDER=your_email@gmail.com

# Dev mode: print verification codes to terminal instead of sending email
DEV_EMAIL_MODE=True

# Google Sheets (optional)
# GOOGLE_SHEET_ID=your_sheet_id
# SERVICE_ACCOUNT_JSON_PATH=service_account.json
```

### 5. Start the servers

```powershell
.\start.ps1
```

This opens two PowerShell windows:

- **Flask backend** → `http://localhost:5000`
- **Django frontend** → `http://localhost:8000`

Open **`http://localhost:8000`** in your browser.

> **Note:** Do NOT use the VS Code Simple Browser — it blocks some requests.

> **Tip:** If `DEV_EMAIL_MODE=True`, verification codes are printed in the Flask terminal window.

---

## API Endpoints

### Authentication — Students

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/students/register` | Register (triggers email verification) |
| POST | `/api/students/verify-email` | Submit 6-digit code |
| POST | `/api/students/resend-verification` | Resend code |
| POST | `/api/students/login` | Login, returns JWT |

### Authentication — Admins

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/admins/register` | Register admin |
| POST | `/api/admins/verify-email` | Verify admin email |
| POST | `/api/admins/login` | Login, returns JWT |
| GET | `/api/admin/students` | List all student accounts |
| DELETE | `/api/admin/students/<email>` | Delete a student account |

### Print Requests

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/print-requests/my-requests` | Student: list own requests |
| POST | `/api/print-requests` | Student: submit new request |
| GET | `/api/print-requests/<id>` | Get single request details |
| DELETE | `/api/print-requests/<id>` | Student: delete own pending/revision/rejected request |
| GET | `/api/print-requests/<id>/history` | Get status change history |

### File Uploads

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/print-requests/upload-stl` | Upload `.stl` file, returns filename |
| DELETE | `/api/print-requests/upload-stl/<filename>` | Delete uploaded STL |
| POST | `/api/print-requests/upload-ufp` | Upload `.ufp` file (admin), returns parsed slice data |
| DELETE | `/api/print-requests/upload-ufp/<filename>` | Delete uploaded UFP |
| GET | `/api/uploads/<filename>` | Serve uploaded file |

### Admin Actions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/print-requests` | List all requests |
| PATCH | `/api/admin/print-requests/<id>/status` | Update request status |
| POST | `/api/admin/print-requests/<id>/return` | Send feedback (sets status to `revision_requested`) |
| POST | `/api/admin/print-requests/<id>/approve-with-ufp` | Approve with UFP slice data |
| GET | `/api/admin/print-requests/statistics` | Dashboard statistics |

### 2FA (TOTP)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/2fa/status` | Check if 2FA is enabled |
| POST | `/api/2fa/setup` | Generate TOTP secret + QR code |
| POST | `/api/2fa/confirm` | Confirm 2FA setup with a TOTP code |
| POST | `/api/2fa/verify` | Verify TOTP code during login |
| DELETE | `/api/2fa/disable` | Disable 2FA |

### Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/reports/sync-google-sheet` | Sync data from Google Sheet |
| GET | `/api/reports/weekly` | Weekly report summary |
| GET | `/api/reports/raw` | Raw print log data |
| GET | `/api/reports/printer/<name>` | Per-printer report |
| GET | `/api/reports/operator/<name>` | Per-operator report |
| GET | `/api/reports/materials` | Material usage report |
| GET | `/api/reports/errors` | Error tracking report |
| GET | `/api/reports/monthly` | Monthly report |

---

## Request Status Workflow

```
  [Pending] -----> [Approved] -----> [In Progress] -----> [Completed]
      |                                    |
      +-----> Rejected                     +-----> Cancelled
      |
      +-----> Revision Requested -----> (student resubmits) -----> Pending
```

---

## Admin Review Workflow

When an admin opens a pending request, the review panel is shown immediately:

1. **Download the STL** — click the download link, open in Cura
2. **Slice & check** — if the model is printable, slice it and save as `.ufp`
3. **Decision:**
   - ✅ **Approve** — upload the `.ufp` file, optionally add notes, click Approve
   - ↩ **Send Back** — write feedback in the notes field, click Send Back
   - ❌ **Reject** — click Reject to permanently reject

---

## Email Verification

**Dev mode** (`DEV_EMAIL_MODE=True`):

- No real email is sent
- Code appears in the Flask terminal window: `[DEV] Verification code for user@email.com: 483921`

**Production mode** (`DEV_EMAIL_MODE=False`):

1. Google Account → Security → **App Passwords** → generate 16-char password
2. Fill in `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER` in `.env`
3. Set `DEV_EMAIL_MODE=False` and restart Flask

---

## Reset a Password (Dev)

Use Python directly — never use PowerShell mysql with `$` in the value (escaping corrupts bcrypt hashes):

```python
import bcrypt, mysql.connector
conn = mysql.connector.connect(host="127.0.0.1", user="root", password="password", database="DGSpace")
cursor = conn.cursor()
new_hash = bcrypt.hashpw(b"yournewpassword", bcrypt.gensalt()).decode()
cursor.execute("UPDATE students SET password_hash=%s WHERE email=%s", (new_hash, "user@email.com"))
# For admin accounts: UPDATE admins SET password_hash=...
conn.commit()
print("Done")
```

---

## Security Notes

- Never commit `.env` (add to `.gitignore`)
- JWT tokens stored in browser `localStorage` (`dg_token`, `dg_user`)
- Token expiry: 24 hours
- Verification codes expire in 15 minutes
- Passwords hashed with bcrypt (12 rounds)
- STL files stored with UUID filenames to prevent path traversal

---

## Google Sheets Report Integration

The manager can sync the Google Sheet (where staff record print jobs) into the database and view aggregated weekly KPI reports.

```
Google Sheet --> /api/reports/sync-google-sheet --> print_logs_raw --> /reports/weekly/
```

### Setting Up a Service Account (One-Time)

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials**
2. Click **Create Credentials → Service Account**
3. Open the new Service Account → **Keys** tab → **Add Key → Create new key (JSON)**
4. Download and save the JSON file (e.g. `backend/service_account.json`)
5. Enable the **Google Sheets API** in **APIs & Services → Library**

### Sharing the Sheet

1. Open the JSON key file, find `"client_email"` (e.g. `dgspace@project.iam.gserviceaccount.com`)
2. Open your Google Sheet → **Share** → paste that email → set permission to **Viewer**
3. Copy the Sheet ID from the URL and add to `.env`:

```ini
GOOGLE_SHEET_ID=your_sheet_id_here
GOOGLE_SHEET_TAB_NAME=Sheet1
SERVICE_ACCOUNT_JSON_PATH=backend/service_account.json
```

---

## License

This project is developed for Donald's Garage at the University of Tampa.
