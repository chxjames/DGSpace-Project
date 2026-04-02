# DGSpace — 3D Print Request Management System

A full-stack web application for **Donald's Garage** at the University of San Diego. Students submit 3D print requests and admins review, slice, and manage them through a streamlined workflow.

**Live:**
- Frontend: https://dgspace-c5ff.up.railway.app
- Backend API: https://dgspace-project-production.up.railway.app

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Django 5.2 (template rendering) |
| Backend API | Python Flask 3.0 (REST API) |
| Database | MySQL 8.0 (AWS RDS) |
| Auth | JWT tokens + bcrypt + Email verification + TOTP 2FA |
| 3D Viewer | Three.js 0.165 (STL preview in browser) |
| UFP Parsing | Custom parser for Cura `.ufp` slice data |
| Reports | Dashboard from `print_requests` DB table |
| Hosting | Railway (both services, auto-deploy on push to `main`) |
| Python env | virtualenv (`.venv/`) |

---

## Project Structure

```
DGSpace-Project-1/
├── start.ps1                  # Start both servers locally
├── .venv/                     # Shared Python virtual environment
│
├── backend/                   # Flask REST API
│   ├── app.py                 # All API routes
│   ├── auth_service.py        # Register / login / JWT logic
│   ├── email_service.py       # Email verification (Gmail SMTP)
│   ├── print_service.py       # Print request CRUD
│   ├── totp_service.py        # 2FA (TOTP) — setup, verify, disable
│   ├── ufp_analysis.py        # Parse Cura .ufp files (print time, material, etc.)
│   ├── database.py            # MySQL connection wrapper
│   ├── config.py              # Loads settings from .env
│   ├── uploads/               # Uploaded STL & UFP files (UUID-named)
│   ├── .env                   # Local secrets (not committed)
│   └── requirements.txt       # Python dependencies
│
├── frontend/                  # Django frontend
│   ├── manage.py
│   ├── donaldsgarage/         # Django project settings & URL routing
│   ├── accounts/              # Views + API proxy to Flask
│   └── templates/
│       ├── base.html                  # Layout, CSS, shared JS helpers
│       ├── home.html                  # Landing / dashboard
│       ├── profile.html               # User profile: stats, print history, 2FA, change password
│       ├── print_requests.html        # Request list (student & admin)
│       ├── print_request_new.html     # Student: submit new request
│       ├── print_request_detail.html  # Detail page + Three.js STL viewer + admin actions
│       ├── admin_students.html        # Admin: student management + search
│       ├── manage_printers.html       # Admin: printer management
│       ├── manage_admins.html         # Admin: admin account management + password reset
│       ├── weekly_report.html         # Reports dashboard
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
  | HTTP (Railway)
  v
Django Frontend
  |- Serves HTML templates
  |- /api/* --> proxied to Flask (ApiProxyView)
                    |
                    v
                Flask Backend (Railway)
                    |- REST API
                    v
                 MySQL (AWS RDS)
```

All browser JS uses relative URLs (`/api/...`) — everything routes through Django, no CORS issues.

---

## Features

### Student Side

- **Register & Login** — Email verification required
- **2FA Required** — After first login, users must set up TOTP 2FA before accessing any features
- **Submit Print Request** — Upload `.stl` file, choose material/color, set optional deadline
- **3D STL Preview** — Interactive Three.js viewer on the detail page (rotate, zoom)
- **Track Status** — See request status (Pending → Approved → In Progress → Completed)
- **Receive Feedback** — Admin feedback displayed with revision instructions
- **Profile Page** — View personal info, print history (filterable), manage 2FA, change password

### Admin Side

- **Review Requests** — Unified review panel shown immediately on detail page:
  - Download STL → Slice in Cura → Upload `.ufp` → Approve
  - Or write feedback in notes → Send Back for revision
  - Or Reject outright
- **UFP Slice Data** — Auto-parsed from Cura `.ufp` files (print time, material weight, layer height, infill)
- **Student Management** — Search/filter students, promote to Staff, reset 2FA, delete accounts
- **Admin Management** — Create admin accounts (pre-set credentials), reset any admin's password, manage roles
- **Printer Management** — Track printer inventory
- **Dashboard** — Live stats strip (Pending / Approved / In Progress / Completed / Total) on homepage
- **Reports** — Aggregated stats (requests by status, material usage, top students, daily breakdown)

### Security

- JWT authentication with 24-hour token expiry
- Passwords hashed with bcrypt (12 rounds)
- Email verification (6-digit code, 15-minute expiry)
- **TOTP 2FA enforced** — All users must enable 2FA before accessing any feature; compatible with Google Authenticator, Duo, Microsoft Authenticator
- Admin can reset any user's 2FA from the management pages
- File upload validation (type, size limits)

---

## User Roles

| Role | Access |
|---|---|
| `student` | Submit & track own print requests |
| `student_staff` | Manage all print requests (same as admin for requests) |
| `admin` | Full access: students, printers, admins, reports |
| `professor` / `manager` | Reports access |

---

## 2FA Flow

```
First login (no 2FA set up)
  └── Home page shows locked state → "Go to Profile & Set Up 2FA"
         └── Profile page: scan QR code with authenticator app → enter code to confirm
                └── 2FA active → all features unlocked

Subsequent logins
  └── Login with email + password → JWT issued → home page shows full dashboard
```

- Users can disable their own 2FA from the Profile page (no code required, just confirmation)
- Admins can force-reset any student's 2FA from the Students page (🔑 Reset 2FA button)
- Admins can force-reset any admin's 2FA from the Admins page (🔑 Reset 2FA button)

---

## Prerequisites

- **Python 3.10+**
- **MySQL 8.0+** (local dev) or AWS RDS (production)
- **Cura** (for slicing STL → UFP files, admin workflow)

---

## Local Development Setup

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
```

Then run any `migration_*.sql` files in order.

Tables: `students`, `admins`, `email_verification_codes`, `password_reset_tokens`, `totp_secrets`, `print_requests`, `print_request_history`, `printers`

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
```

### 5. Start the servers

```powershell
.\start.ps1
```

This opens two PowerShell windows:

- **Flask backend** → `http://localhost:5000`
- **Django frontend** → `http://localhost:8000`

Open **`http://localhost:8000`** in your browser.

> **Tip:** If `DEV_EMAIL_MODE=True`, verification codes print in the Flask terminal window.

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
| POST | `/api/admins/login` | Login, returns JWT |
| GET | `/api/admin/admins` | List all admin accounts |
| POST | `/api/admin/admins` | Create new admin account |
| DELETE | `/api/admin/admins/<email>` | Delete an admin account |
| PATCH | `/api/admin/admins/<email>/password` | Reset an admin's password |

### Student Management (Admin)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/students` | List all student accounts |
| PATCH | `/api/admin/students/<email>/role` | Promote/demote student role |
| DELETE | `/api/admin/students/<email>` | Delete a student account |
| DELETE | `/api/admin/students/<email>/2fa` | Force-reset a student's 2FA |

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

### Profile

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profile` | Get current user's profile info |
| POST | `/api/profile/change-password` | Change own password (requires current password) |

### 2FA (TOTP)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/2fa/status` | Check if 2FA is enabled |
| POST | `/api/2fa/setup` | Generate TOTP secret + QR code |
| POST | `/api/2fa/confirm` | Confirm 2FA setup with first TOTP code |
| DELETE | `/api/2fa/disable` | Disable own 2FA (JWT only, no code required) |

### Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports/dashboard` | Aggregated stats from print_requests (by status, material, day, top students) |

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
- Code appears in the Flask terminal: `[DEV] Verification code for user@email.com: 483921`

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
- STL/UFP files stored with UUID filenames to prevent path traversal
- 2FA is enforced at the UI level — users without 2FA can log in but cannot access any features until 2FA is set up

---

## License

This project is developed for Donald's Garage at the University of San Diego.


A full-stack web application for **Donald's Garage** at the University of San Diego. Students submit 3D print requests and admins review, slice, and manage them through a streamlined workflow.

**Live:**
- Frontend: https://dgspace-c5ff.up.railway.app
- Backend API: https://dgspace-project-production.up.railway.app

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Django 5.2 (template rendering) |
| Backend API | Python Flask 3.0 (REST API) |
| Database | MySQL 8.0 (AWS RDS) |
| Auth | JWT tokens + bcrypt + Email verification + TOTP 2FA |
| 3D Viewer | Three.js 0.165 (STL preview in browser) |
| UFP Parsing | Custom parser for Cura `.ufp` slice data |
| Reports | Dashboard from `print_requests` DB table |
| Hosting | Railway (both services) |
| Python env | virtualenv (`.venv/`) |

---

## Project Structure

```
DGSpace-Project-1/
├── start.ps1                  # Start both servers locally
├── .venv/                     # Shared Python virtual environment
│
├── backend/                   # Flask REST API
│   ├── app.py                 # All API routes
│   ├── auth_service.py        # Register / login / JWT logic
│   ├── email_service.py       # Email verification (Gmail SMTP)
│   ├── print_service.py       # Print request CRUD
│   ├── totp_service.py        # 2FA (TOTP) — setup, verify, disable
│   ├── ufp_analysis.py        # Parse Cura .ufp files (print time, material, etc.)
│   ├── database.py            # MySQL connection wrapper
│   ├── config.py              # Loads settings from .env
│   ├── uploads/               # Uploaded STL & UFP files (UUID-named)
│   ├── .env                   # Local secrets (not committed)
│   └── requirements.txt       # Python dependencies
│
├── frontend/                  # Django frontend
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
│       ├── manage_printers.html       # Admin: printer management
│       ├── manage_admins.html         # Admin: admin account management
│       ├── weekly_report.html         # Reports dashboard
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
  | HTTP (Railway)
  v
Django Frontend
  |- Serves HTML templates
  |- /api/* --> proxied to Flask (ApiProxyView)
                    |
                    v
                Flask Backend (Railway)
                    |- REST API
                    v
                 MySQL (AWS RDS)
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
- **Reports Dashboard** — Aggregated stats (requests by status, material usage, top students) read directly from the database

### Security

- JWT authentication with 24-hour token expiry
- Passwords hashed with bcrypt
- Email verification (6-digit code, 15-minute expiry)
- Optional TOTP 2FA (Google Authenticator compatible)
- File upload validation (type, size limits)

---

## Prerequisites

- **Python 3.10+**
- **MySQL 8.0+** (local dev) or AWS RDS (production)
- **Cura** (for slicing STL → UFP files, admin workflow)

---

## Local Development Setup

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
```

Then run any `migration_*.sql` files in order.

Tables: `students`, `admins`, `email_verification_codes`, `password_reset_tokens`, `totp_secrets`, `print_requests`, `print_request_history`, `printers`

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
```

### 5. Start the servers

```powershell
.\start.ps1
```

This opens two PowerShell windows:

- **Flask backend** → `http://localhost:5000`
- **Django frontend** → `http://localhost:8000`

Open **`http://localhost:8000`** in your browser.

> **Tip:** If `DEV_EMAIL_MODE=True`, verification codes print in the Flask terminal window.

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
| GET | `/api/reports/dashboard` | Aggregated stats from print_requests (by status, material, day, top students) |

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

## License

This project is developed for Donald's Garage at the University of San Diego.
