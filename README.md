# DGSpace — 3D Print Request Management System

A web application for Donald's Garage that lets students submit 3D print requests and admins review and manage them.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Django 5.2 (template rendering, port 8000) |
| Backend API | Python Flask 3.0 (REST API, port 5000) |
| Database | MySQL 8.0 (local) |
| Auth | JWT tokens + bcrypt + Email verification + TOTP 2FA |
| STL Analysis | numpy-stl (volume, weight, print time estimation) |
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
│   ├── stl_analysis.py        # STL file analysis (volume/weight/time)
│   ├── totp_service.py        # 2FA (TOTP) — setup, verify, disable
│   ├── database.py            # MySQL connection wrapper
│   ├── config.py              # Loads settings from .env
│   ├── uploads/               # Uploaded STL files (UUID-named)
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
│       ├── print_request_return.html  # Admin: send feedback to student
│       ├── admin_students.html        # Admin: student management
│       └── registration/
│           ├── login.html
│           └── signup.html
└── database/
    ├── schema.sql             # Full DB schema (7 tables)
    ├── migration_001_print_requests.sql
    ├── migration_002_stl_upload.sql   # Adds stl_file_path, stl_original_name
    └── migration_003_revision_requested.sql  # Adds revision_requested status
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

## STL Analysis

When a student uploads an `.stl` file, the backend automatically analyzes it using **numpy-stl** and returns:

| Metric | Description |
| --- | --- |
| Volume (cm³) | Calculated via signed tetrahedra method |
| Bounding box | X × Y × Z dimensions in mm |
| Est. Weight (g) | Based on material density and infill |
| Est. Print Time (h) | Based on deposited volume and material-specific print speed |

**Supported materials & print speeds:**

| Material | Density (g/cm³) | Print Speed (mm³/s) |
| --- | --- | --- |
| PLA | 1.24 | 5.0 |
| ABS | 1.04 | 4.5 |
| PETG | 1.27 | 4.0 |
| TPU | 1.21 | 2.5 |
| Nylon | 1.14 | 3.5 |
| Resin | 1.10 | 8.0 |

Students can adjust the **infill slider** (5–100%) on the new request form — estimates update in real-time (on mouse release). The detail page displays the infill value used at submission.

### Estimation Formula

**Step 1 — Model volume:** `numpy-stl` calculates the total enclosed volume (`V_mm3`) using the signed tetrahedra method.

**Step 2 — Effective solid fraction:** A print is not 100% solid. The outer shell (~30%) is fully solid, while the interior is filled at the user-selected infill ratio:

```
effective_solid = 0.30 + 0.70 × infill
```

**Step 3 — Deposited volume:**

```
deposited_mm3 = V_mm3 × effective_solid
```

**Step 4 — Weight estimate:**

```
W_grams = (deposited_mm3 / 1000) × density_g_per_cm3
```

**Step 5 — Print time estimate** (with 1.35× overhead for travel moves, retraction, homing, etc.):

```
T_hours = (V_mm3 × [0.30 + 0.70 × infill]) / speed_mm3_per_s × 1.35 / 3600
```

where `speed_mm3_per_s` is the material-specific print speed from the table above.

> **⚠️ Limitations:** These are rough estimates. Actual values depend on slicer settings (Cura/PrusaSlicer), wall/infill speed differences, support structures, heating/cooling time, and printer kinematics.

---

## Request Statuses

| Status | Description |
| --- | --- |
| `pending` | Newly submitted, awaiting admin review |
| `approved` | Admin approved — ready to print |
| `rejected` | Admin rejected the request (student can delete) |
| `in_progress` | Print job is running |
| `completed` | Print finished |
| `cancelled` | Cancelled by admin |
| `revision_requested` | Admin sent feedback — student should revise and resubmit |

### Admin Workflow

Admins manage requests directly on the **detail page** (`/print-requests/<id>/`). An action panel appears at the bottom:

| Current Status | Available Actions |
| --- | --- |
| `pending` / `revision_requested` | ✅ Approve (Ready to Print), ❌ Reject, 💬 Send Feedback |
| `approved` / `in_progress` | ✅ Mark Completed, 🚫 Cancel |
| `completed` / `rejected` / `cancelled` | No actions (read-only) |

### Student Permissions

Students can **delete** their own requests when the status is `pending`, `revision_requested`, or `rejected`.

---

## Pages

| URL | Description |
| --- | --- |
| `/` | Home / dashboard |
| `/accounts/login/` | Log in |
| `/accounts/signup/` | Sign up |
| `/print-requests/` | My print requests |
| `/print-requests/new/` | Submit new request |
| `/print-requests/<id>/` | Request detail + Three.js STL preview + STL analysis + admin actions |
| `/print-requests/<id>/return/` | Admin: send feedback (legacy, now integrated in detail page) |
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
| POST | `/api/print-requests/upload-stl` | Student: upload `.stl` file, returns `filename` + auto-analysis |
| DELETE | `/api/print-requests/upload-stl/<filename>` | Delete an uploaded STL file |
| GET | `/api/print-requests/analyze-stl/<filename>` | Analyze STL: volume, weight, print time (accepts `?material=PLA&infill=0.2`) |
| GET | `/api/print-requests/<id>` | Get single request details (includes `stl_file_path`) |
| DELETE | `/api/print-requests/<id>` | Student: delete own **pending**, **revision_requested**, or **rejected** request (also deletes uploaded STL) |
| GET | `/api/uploads/<filename>` | Serve uploaded STL files |
| GET | `/api/admin/print-requests` | Admin: list all requests |
| PATCH | `/api/admin/print-requests/<id>/status` | Admin: update request status |
| POST | `/api/admin/print-requests/<id>/return` | Admin: send feedback (sets status to `revision_requested`) |
| GET | `/api/admin/print-requests/statistics` | Admin: dashboard statistics |

### 2FA (TOTP)

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/2fa/status` | Check if 2FA is enabled |
| POST | `/api/2fa/setup` | Generate TOTP secret + QR code |
| POST | `/api/2fa/confirm` | Confirm 2FA setup with a TOTP code |
| POST | `/api/2fa/verify` | Verify TOTP code during login |
| DELETE | `/api/2fa/disable` | Disable 2FA |

---

## First-Time Setup

### 1. Database

```powershell
$mysql = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
& $mysql -u root -p DGSpace < database/schema.sql
& $mysql -u root -p DGSpace < database/migration_001_print_requests.sql
& $mysql -u root -p DGSpace < database/migration_002_stl_upload.sql
& $mysql -u root -p DGSpace < database/migration_003_revision_requested.sql
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
- TOTP 2FA is implemented in `totp_service.py` with API endpoints for setup/verify/disable
- STL files stored with UUID filenames to prevent path traversal

---

## Weekly Report — Google Sheet Integration

### How It Works

The manager can sync the Google Sheet (where staff record print jobs) directly into the database and view aggregated weekly KPI reports.

**Data flow:**
```
Google Sheet → /api/reports/sync-google-sheet → print_logs_raw + print_logs_normalized → /reports/weekly/
```

**Report pages:**
| URL | Description |
|-----|-------------|
| `/reports/weekly/` | Weekly KPI dashboard (Volume / Material / Capacity / Staffing) |
| `/reports/sync/` | Trigger a Sheet sync |
| `/reports/raw/` | Inspect raw imported rows, see parse warnings |

---

### Setting Up Google Service Account (One-Time)

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials**
2. Click **Create Credentials → Service Account**, give it any name
3. Open the new Service Account → **Keys** tab → **Add Key → Create new key (JSON)**
4. Download the JSON file. Save it somewhere safe (e.g. `backend/service_account.json`)
5. **Enable the Google Sheets API** in **APIs & Services → Library**

---

### Sharing the Sheet with the Service Account

1. Open the JSON key file, find the `"client_email"` field — it looks like:
   `dgspace-reports@your-project.iam.gserviceaccount.com`
2. Open your Google Sheet → **Share** → paste that email → set permission to **Viewer**
3. Copy the Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/**<SHEET_ID>**/edit`

---

### Environment Variables (`.env`)

Add these to your `.env` file:

```ini
# Google Sheets
GOOGLE_SHEET_ID=your_sheet_id_here
GOOGLE_SHEET_TAB_NAME=Sheet1
SERVICE_ACCOUNT_JSON_PATH=backend/service_account.json
```

---

### Expected Sheet Column Headers

The Sheet must contain these exact column headers (order doesn't matter):

| Column | Header | Notes |
|--------|--------|-------|
| A | `Timestamp` | Auto-filled by Google Forms |
| B | `Email address` | Student email |
| C | `Name` | Student name |
| N | `Operator` | Staff member who handled the job |
| O | `Printer` | Printer name (e.g. "Bambu X1C") |
| P | `Print time (HH:MM)` | Actual print time — any format accepted |
| Q | `Print Consumables (g)` | Material used in grams |
| R | `Date Started` | When printing began |
| S | `Finished?` | Yes/No/True/False/1/0 |
| T | `Error 1` | Optional error note |
| U | `Error 2` | Optional error note |
| — | `Actual Finish` | Optional — staff hand-fills this; highest priority for finished_at |
| — | `File Name` | Optional |

**Print time accepted formats:**
- `8:13:00` → H:MM:SS (493 min)
- `2:05` → H:MM (125 min)
- `:26` → :MM only (26 min)
- `32` → plain number = minutes
- `1 hour 13` → text format (73 min)

---

### Installing New Dependencies

After pulling this update, run:

```bash
pip install -r backend/requirements.txt
```

New packages: `gspread>=6.0.0`, `google-auth>=2.0.0`

---

### Running Database Migrations

```sql
-- Run in order:
SOURCE database/migration_006_add_print_logs.sql;
SOURCE database/migration_007_add_slicer_fields.sql;
```

---

### Cura Slicer Time Field (Students)

The print request form now requires a **Cura Slicer Estimate**:

- **How to find it**: Open the STL file in Cura, apply your material and infill settings, click **Slice**, then read the time and material estimate from the **bottom-right corner** of the Cura window.
- **Estimated Print Time** (required): Enter hours and minutes — e.g. 2 h 13 min
- **Estimated Material** (optional): Enter grams — e.g. 32 g

This value is used to calculate `finished_at` when actual Sheet data is missing.

