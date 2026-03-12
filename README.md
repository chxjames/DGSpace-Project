# DGSpace — 3D Print Request Management System# DGSpace — 3D Print Request Management System



A full-stack web application for **Donald's Garage** that lets students submit 3D print requests and admins review, slice, and manage them through a streamlined workflow.A web application for Donald's Garage that lets students submit 3D print requests and admins review and manage them.



---## Tech Stack



## Tech Stack| Layer | Technology |

|---|---|

| Layer | Technology || Frontend | Django 5.2 (template rendering, port 8000) |

|---|---|| Backend API | Python Flask 3.0 (REST API, port 5000) |

| Frontend | Django 5.2 (template rendering, port 8000) || Database | MySQL 8.0 (local) |

| Backend API | Python Flask 3.0 (REST API, port 5000) || Auth | JWT tokens + bcrypt + Email verification + TOTP 2FA |

| Database | MySQL 8.0 || STL Analysis | numpy-stl (volume, weight, print time estimation) |

| Auth | JWT + bcrypt + Email verification + TOTP 2FA || Python env | virtualenv at `.venv/` |

| 3D Viewer | Three.js 0.165 (STL preview in browser) |

| UFP Parsing | Custom parser for Cura `.ufp` slice data |---

| Reports | Google Sheets integration (weekly print logs) |

| Python env | virtualenv (`.venv/`) |## Project Structure



---```

DGSpace-Project-1/

## Project Structure├── start.ps1                  # <- Start both servers (run this!)

├── .venv/                     # Shared Python virtual environment

```├── backend/                   # Flask REST API (port 5000)

DGSpace-Project-1/│   ├── app.py                 # All API routes

├── start.ps1                  # ← Start both servers (run this!)│   ├── auth_service.py        # Register / login / JWT logic

├── .venv/                     # Shared Python virtual environment│   ├── email_service.py       # Email verification (Gmail SMTP)

││   ├── print_service.py       # Print request logic

├── backend/                   # Flask REST API (port 5000)│   ├── stl_analysis.py        # STL file analysis (volume/weight/time)

│   ├── app.py                 # All API routes│   ├── totp_service.py        # 2FA (TOTP) — setup, verify, disable

│   ├── auth_service.py        # Register / login / JWT logic│   ├── database.py            # MySQL connection wrapper

│   ├── email_service.py       # Email verification (Gmail SMTP)│   ├── config.py              # Loads settings from .env

│   ├── print_service.py       # Print request CRUD│   ├── uploads/               # Uploaded STL files (UUID-named)

│   ├── totp_service.py        # 2FA (TOTP) — setup, verify, disable│   ├── .env                   # Local secrets (not committed)

│   ├── ufp_analysis.py        # Parse Cura .ufp files (print time, material, etc.)│   └── requirements.txt       # Python dependencies

│   ├── sheet_service.py       # Google Sheets API wrapper├── frontend/                  # Django frontend (port 8000)

│   ├── report_service.py      # Weekly/monthly report aggregation│   ├── manage.py

│   ├── database.py            # MySQL connection wrapper│   ├── donaldsgarage/         # Django project settings & URLs

│   ├── config.py              # Loads settings from .env│   ├── accounts/              # Views, URL routing, API proxy

│   ├── uploads/               # Uploaded STL & UFP files (UUID-named)│   └── templates/             # HTML pages

│   ├── .env                   # Local secrets (not committed)│       ├── base.html          # Layout, CSS, JS helpers

│   └── requirements.txt       # Python dependencies│       ├── home.html          # Landing / dashboard

││       ├── print_requests.html

├── frontend/                  # Django frontend (port 8000)│       ├── print_request_new.html

│   ├── manage.py│       ├── print_request_detail.html  # Detail + Three.js STL viewer

│   ├── donaldsgarage/         # Django project settings & URL routing│       ├── print_request_return.html  # Admin: send feedback to student

│   ├── accounts/              # Views + API proxy to Flask│       ├── admin_students.html        # Admin: student management

│   └── templates/│       └── registration/

│       ├── base.html                  # Layout, CSS, shared JS helpers│           ├── login.html

│       ├── home.html                  # Landing / dashboard│           └── signup.html

│       ├── print_requests.html        # Request list (student & admin)└── database/

│       ├── print_request_new.html     # Student: submit new request    ├── schema.sql             # Full DB schema (7 tables)

│       ├── print_request_detail.html  # Detail page + Three.js STL viewer    ├── migration_001_print_requests.sql

│       ├── admin_students.html        # Admin: student management    ├── migration_002_stl_upload.sql   # Adds stl_file_path, stl_original_name

│       ├── weekly_report.html         # Weekly print report    └── migration_003_revision_requested.sql  # Adds revision_requested status

│       ├── report_sync.html           # Google Sheets sync UI```

│       ├── report_raw.html            # Raw data view

│       └── registration/---

│           ├── login.html

│           └── signup.html## How to Start

│

└── database/### Every session

    ├── schema.sql             # Full database schema

    └── migration_*.sql        # Incremental migrations**Option A** — right-click `start.ps1` → Run with PowerShell

```

**Option B** — PowerShell terminal:

---

```powershell

## Architecture# Stop any old Python processes first

Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

```

Browser (port 8000)# Start both servers

   │powershell -ExecutionPolicy Bypass -File e:\DGSpace-Project-1\start.ps1

   ├─ HTML pages ← Django template rendering```

   │

   └─ /api/* requestsThis opens **two PowerShell windows**:

        │

        └─ Django ApiProxyView ──→ Flask REST API (port 5000)- Flask backend → `http://localhost:5000` (keep open — shows verification codes)

                                        │- Django frontend → `http://localhost:8000`

                                        └─ MySQL 8.0

```Then open **`http://localhost:8000`** in your browser.



Django serves HTML pages and proxies all `/api/*` requests to the Flask backend. The frontend uses vanilla JS (no React/Vue) with `fetch()` calls. Authentication is handled via JWT tokens stored in `localStorage`.> **Note:** Do NOT use the VS Code Simple Browser — it blocks some requests.



------



## Features## Architecture



### Student Side```

- **Register & Login** — Email verification required; optional TOTP 2FABrowser

- **Submit Print Request** — Upload `.stl` file, choose material/color, set optional deadline  |

- **3D STL Preview** — Interactive Three.js viewer on the detail page (rotate, zoom)  | HTTP to localhost:8000

- **Track Status** — See request status (Pending → Approved → In Progress → Completed)  v

- **Receive Feedback** — Admin feedback displayed with revision instructionsDjango (port 8000)

  |- Serves HTML templates

### Admin Side  |- /api/* --> proxied to Flask (ApiProxyView, csrf_exempt)

- **Review Requests** — Unified review panel shown immediately on detail page                    |

  - Download STL → Slice in Cura → Upload `.ufp` → Approve                    v

  - Or write feedback in notes → Send Back for revision                Flask (port 5000)

  - Or Reject outright                    |- REST API

- **UFP Slice Data** — Auto-parsed from Cura `.ufp` files (print time, material weight, layer height, infill)                    v

- **Student Management** — View/delete student accounts                 MySQL (DGSpace)

- **Status Workflow** — `pending` → `approved` → `in_progress` → `completed` (or `rejected` / `cancelled`)```

- **Reports Dashboard** — Weekly/monthly reports synced from Google Sheets (printer utilization, operator stats, material usage, error tracking)

All browser JS uses relative URLs (`/api/...`) — everything routes through Django, no CORS issues.

### Security

- JWT authentication with 24-hour token expiry---

- Passwords hashed with bcrypt

- Email verification (6-digit code, 15-minute expiry)## STL Analysis

- Optional TOTP 2FA (Google Authenticator compatible)

- File upload validation (type, size limits)When a student uploads an `.stl` file, the backend automatically analyzes it using **numpy-stl** and returns:



---| Metric | Description |

| --- | --- |

## Prerequisites| Volume (cm³) | Calculated via signed tetrahedra method |

| Bounding box | X × Y × Z dimensions in mm |

- **Python 3.10+**| Est. Weight (g) | Based on material density and infill |

- **MySQL 8.0+** (running locally)| Est. Print Time (h) | Based on deposited volume and material-specific print speed |

- **Cura** (for slicing STL → UFP files, admin workflow)

**Supported materials & print speeds:**

---

| Material | Density (g/cm³) | Print Speed (mm³/s) |

## Setup| --- | --- | --- |

| PLA | 1.24 | 5.0 |

### 1. Clone the repository| ABS | 1.04 | 4.5 |

| PETG | 1.27 | 4.0 |

```bash| TPU | 1.21 | 2.5 |

git clone https://github.com/chxjames/DGSpace-Project.git| Nylon | 1.14 | 3.5 |

cd DGSpace-Project| Resin | 1.10 | 8.0 |

```

Students can adjust the **infill slider** (5–100%) on the new request form — estimates update in real-time (on mouse release). The detail page displays the infill value used at submission.

### 2. Create the virtual environment

### Estimation Formula

```powershell

python -m venv .venv**Step 1 — Model volume:** `numpy-stl` calculates the total enclosed volume (`V_mm3`) using the signed tetrahedra method.

.\.venv\Scripts\activate

pip install -r backend/requirements.txt**Step 2 — Effective solid fraction:** A print is not 100% solid. The outer shell (~30%) is fully solid, while the interior is filled at the user-selected infill ratio:

pip install django

``````

effective_solid = 0.30 + 0.70 × infill

### 3. Set up the database```



```sql**Step 3 — Deposited volume:**

-- In MySQL shell:

SOURCE database/schema.sql;```

deposited_mm3 = V_mm3 × effective_solid

-- Run migrations in order:```

SOURCE database/migration_001_print_requests.sql;

SOURCE database/migration_002_stl_upload.sql;**Step 4 — Weight estimate:**

SOURCE database/migration_003_revision_requested.sql;

SOURCE database/migration_004_senior_design_fields.sql;```

SOURCE database/migration_004_add_professor_manager.sql;W_grams = (deposited_mm3 / 1000) × density_g_per_cm3

SOURCE database/migration_005_ufp_fields.sql;```

SOURCE database/migration_006_add_print_logs.sql;

SOURCE database/migration_006_deadline.sql;**Step 5 — Print time estimate** (with 1.35× overhead for travel moves, retraction, homing, etc.):

SOURCE database/migration_007_add_slicer_fields.sql;

```

-- Create a database user:T_hours = (V_mm3 × [0.30 + 0.70 × infill]) / speed_mm3_per_s × 1.35 / 3600

CREATE USER 'dgspace_user'@'localhost' IDENTIFIED BY 'your_password';```

GRANT ALL PRIVILEGES ON DGSpace.* TO 'dgspace_user'@'localhost';

FLUSH PRIVILEGES;where `speed_mm3_per_s` is the material-specific print speed from the table above.

```

> **⚠️ Limitations:** These are rough estimates. Actual values depend on slicer settings (Cura/PrusaSlicer), wall/infill speed differences, support structures, heating/cooling time, and printer kinematics.

### 4. Configure environment variables

---

Create `backend/.env`:

## Request Statuses

```env

# Database| Status | Description |

DB_HOST=localhost| --- | --- |

DB_PORT=3306| `pending` | Newly submitted, awaiting admin review |

DB_USER=dgspace_user| `approved` | Admin approved — ready to print |

DB_PASSWORD=your_password| `rejected` | Admin rejected the request (student can delete) |

DB_NAME=DGSpace| `in_progress` | Print job is running |

| `completed` | Print finished |

# JWT| `cancelled` | Cancelled by admin |

JWT_SECRET_KEY=your_random_secret_key| `revision_requested` | Admin sent feedback — student should revise and resubmit |



# Email (Gmail SMTP example)### Admin Workflow

MAIL_SERVER=smtp.gmail.com

MAIL_PORT=587Admins manage requests directly on the **detail page** (`/print-requests/<id>/`). An action panel appears at the bottom:

MAIL_USE_TLS=True

MAIL_USERNAME=your_email@gmail.com| Current Status | Available Actions |

MAIL_PASSWORD=your_app_password| --- | --- |

MAIL_DEFAULT_SENDER=your_email@gmail.com| `pending` / `revision_requested` | ✅ Approve (Ready to Print), ❌ Reject, 💬 Send Feedback |

| `approved` / `in_progress` | ✅ Mark Completed, 🚫 Cancel |

# Dev mode: print verification codes to terminal instead of sending email| `completed` / `rejected` / `cancelled` | No actions (read-only) |

DEV_EMAIL_MODE=True

### Student Permissions

# Google Sheets (optional — for reports)

# GOOGLE_SHEET_ID=your_sheet_idStudents can **delete** their own requests when the status is `pending`, `revision_requested`, or `rejected`.

# SERVICE_ACCOUNT_JSON_PATH=service_account.json

```---



### 5. Start the servers## Pages



```powershell| URL | Description |

.\start.ps1| --- | --- |

```| `/` | Home / dashboard |

| `/accounts/login/` | Log in |

This opens two PowerShell windows:| `/accounts/signup/` | Sign up |

- **Flask backend** on `http://localhost:5000`| `/print-requests/` | My print requests |

- **Django frontend** on `http://localhost:8000`| `/print-requests/new/` | Submit new request |

| `/print-requests/<id>/` | Request detail + Three.js STL preview + STL analysis + admin actions |

Open your browser and go to **http://localhost:8000**.| `/print-requests/<id>/return/` | Admin: send feedback (legacy, now integrated in detail page) |

| `/admin/students/` | Admin-only student accounts list + delete |

> **Tip:** If `DEV_EMAIL_MODE=True`, verification codes are printed in the Flask terminal window.

---

---

## API Endpoints

## API Endpoints

### Students

### Authentication

| Method | Endpoint | Description |

| Method | Endpoint | Description || --- | --- | --- |

|--------|----------|-------------|| POST | `/api/students/register` | Register (triggers email verification) |

| POST | `/api/students/register` | Register a student || POST | `/api/students/verify-email` | Submit 6-digit code |

| POST | `/api/students/verify-email` | Verify email with code || POST | `/api/students/resend-verification` | Resend code |

| POST | `/api/students/login` | Student login (returns JWT) || POST | `/api/students/login` | Login, returns JWT |

| POST | `/api/students/resend-verification` | Resend verification code |

| POST | `/api/admins/register` | Register an admin |### Admins

| POST | `/api/admins/verify-email` | Verify admin email |

| POST | `/api/admins/login` | Admin login (returns JWT) || Method | Endpoint | Description |

| GET  | `/api/profile` | Get current user profile || --- | --- | --- |

| POST | `/api/admins/register` | Register admin |

### Print Requests| POST | `/api/admins/verify-email` | Verify admin email |

| POST | `/api/admins/login` | Login, returns JWT |

| Method | Endpoint | Description || GET | `/api/admin/students` | List all student accounts |

|--------|----------|-------------|| DELETE | `/api/admin/students/<email>` | Delete a student account (also deletes their print requests) |

| POST   | `/api/print-requests` | Create a new request |

| GET    | `/api/print-requests/my-requests` | List student's own requests |### Print Requests

| GET    | `/api/print-requests/<id>` | Get request detail |

| DELETE | `/api/print-requests/<id>` | Delete own request || Method | Endpoint | Description |

| GET    | `/api/print-requests/<id>/history` | Get status change history || --- | --- | --- |

| GET | `/api/print-requests/my-requests` | Student: list own requests |

### File Uploads| POST | `/api/print-requests` | Student: submit new request (includes optional STL info) |

| POST | `/api/print-requests/upload-stl` | Student: upload `.stl` file, returns `filename` + auto-analysis |

| Method | Endpoint | Description || DELETE | `/api/print-requests/upload-stl/<filename>` | Delete an uploaded STL file |

|--------|----------|-------------|| GET | `/api/print-requests/analyze-stl/<filename>` | Analyze STL: volume, weight, print time (accepts `?material=PLA&infill=0.2`) |

| POST   | `/api/print-requests/upload-stl` | Upload STL file || GET | `/api/print-requests/<id>` | Get single request details (includes `stl_file_path`) |

| DELETE | `/api/print-requests/upload-stl/<filename>` | Delete uploaded STL || DELETE | `/api/print-requests/<id>` | Student: delete own **pending**, **revision_requested**, or **rejected** request (also deletes uploaded STL) |

| POST   | `/api/print-requests/upload-ufp` | Upload UFP file (admin) || GET | `/api/uploads/<filename>` | Serve uploaded STL files |

| DELETE | `/api/print-requests/upload-ufp/<filename>` | Delete uploaded UFP || GET | `/api/admin/print-requests` | Admin: list all requests |

| GET    | `/api/uploads/<filename>` | Serve uploaded file || PATCH | `/api/admin/print-requests/<id>/status` | Admin: update request status |

| POST | `/api/admin/print-requests/<id>/return` | Admin: send feedback (sets status to `revision_requested`) |

### Admin| GET | `/api/admin/print-requests/statistics` | Admin: dashboard statistics |



| Method | Endpoint | Description |### 2FA (TOTP)

|--------|----------|-------------|

| GET    | `/api/admin/students` | List all students || Method | Endpoint | Description |

| DELETE | `/api/admin/students/<email>` | Delete a student || --- | --- | --- |

| GET    | `/api/admin/print-requests` | List all print requests || GET | `/api/2fa/status` | Check if 2FA is enabled |

| PATCH  | `/api/admin/print-requests/<id>/status` | Update request status || POST | `/api/2fa/setup` | Generate TOTP secret + QR code |

| POST   | `/api/admin/print-requests/<id>/return` | Send feedback (revision requested) || POST | `/api/2fa/confirm` | Confirm 2FA setup with a TOTP code |

| POST   | `/api/admin/print-requests/<id>/approve-with-ufp` | Approve with slice data || POST | `/api/2fa/verify` | Verify TOTP code during login |

| GET    | `/api/admin/print-requests/statistics` | Dashboard statistics || DELETE | `/api/2fa/disable` | Disable 2FA |



### 2FA---



| Method | Endpoint | Description |## First-Time Setup

|--------|----------|-------------|

| GET    | `/api/2fa/status` | Check 2FA status |### 1. Database

| POST   | `/api/2fa/setup` | Generate TOTP secret + QR |

| POST   | `/api/2fa/confirm` | Confirm 2FA setup |```powershell

| POST   | `/api/2fa/verify` | Verify TOTP code during login |$mysql = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"

| DELETE | `/api/2fa/disable` | Disable 2FA |& $mysql -u root -p DGSpace < database/schema.sql

& $mysql -u root -p DGSpace < database/migration_001_print_requests.sql

### Reports& $mysql -u root -p DGSpace < database/migration_002_stl_upload.sql

& $mysql -u root -p DGSpace < database/migration_003_revision_requested.sql

| Method | Endpoint | Description |```

|--------|----------|-------------|

| POST   | `/api/reports/sync-google-sheet` | Sync data from Google Sheet |Tables: `students`, `admins`, `email_verification_codes`, `password_reset_tokens`, `totp_secrets`, `print_requests`, `print_request_history`

| GET    | `/api/reports/weekly` | Weekly report summary |

| GET    | `/api/reports/raw` | Raw print log data |### 2. Python environment

| GET    | `/api/reports/printer/<name>` | Per-printer report |

| GET    | `/api/reports/operator/<name>` | Per-operator report |```powershell

| GET    | `/api/reports/materials` | Material usage report |python -m venv .venv

| GET    | `/api/reports/errors` | Error tracking report |.venv\Scripts\pip install -r backend/requirements.txt

| GET    | `/api/reports/monthly` | Monthly report |.venv\Scripts\pip install django requests

```

---

### 3. Create `backend/.env`

## Request Status Workflow

```properties

```DB_HOST=127.0.0.1

  ┌─────────┐      ┌──────────┐      ┌─────────────┐      ┌───────────┐DB_PORT=3306

  │ Pending │─────→│ Approved │─────→│ In Progress │─────→│ Completed │DB_USER=dgspace_user

  └─────────┘      └──────────┘      └─────────────┘      └───────────┘DB_PASSWORD=password

       │                                    │DB_NAME=DGSpace

       ├──→ Rejected                        └──→ Cancelled

       │JWT_SECRET_KEY=dgspace-super-secret-2026-change-in-production

       └──→ Revision Requested ──→ (student resubmits) ──→ Pending

```MAIL_SERVER=smtp.gmail.com

MAIL_PORT=587

---MAIL_USE_TLS=True

MAIL_USERNAME=your-email@gmail.com

## Admin Review WorkflowMAIL_PASSWORD=your-gmail-app-password

MAIL_DEFAULT_SENDER=your-email@gmail.com

When an admin opens a pending request, the review panel is shown immediately:

FLASK_ENV=development

1. **Download the STL** — click the download link, open in CuraPORT=5000

2. **Slice & check** — if the model is printable, slice it and save as `.ufp`

3. **Decision:**# Set to True to print verification codes to terminal instead of emailing

   - ✅ **Approve** — upload the `.ufp` file, optionally add notes, click ApproveDEV_EMAIL_MODE=True

   - ↩ **Send Back** — write feedback in the notes field, click Send Back```

   - ❌ **Reject** — click Reject to permanently reject

---

---

## Email Verification

## License

**Dev mode** (`DEV_EMAIL_MODE=True`):

This project is developed for Donald's Garage at the University of Tampa.

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

