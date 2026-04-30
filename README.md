# DGSpace - Print Request Management System

A full-stack web application for **Donald's Garage** at the University of San Diego. Students submit 3D print and laser cutting requests, and admins review, schedule, and manage them through a streamlined production workflow.

**Live:** <https://dgspace-project-production.up.railway.app>

---

## Tech Stack

| Layer | Technology |
|---|---|
| Server | Python Flask 3.0 (pages + REST API, single service) |
| Templates | Jinja2 (served directly by Flask) |
| Database | MySQL 8.0 (AWS RDS) |
| Auth | JWT tokens + bcrypt + Email verification + TOTP 2FA |
| Email | Gmail API (OAuth2) |
| 3D Viewer | Three.js (STL preview in browser) |
| File Parsing | Custom parsers for Cura `.ufp` and multi-slicer `.3mf` slice data |
| Hosting | Railway (single service, auto-deploy on push to `main`) |

---

## Project Structure

```
DGSpace-Project/
|-- backend/                        # Flask application (single service)
|   |-- app.py                      # App factory, blueprint registration, background scheduler
|   |-- auth_service.py             # Register / login / JWT logic
|   |-- email_service.py            # Gmail API OAuth2 email sending
|   |-- print_service.py            # Print request CRUD + statistics
|   |-- totp_service.py             # 2FA (TOTP) - setup, verify, disable
|   |-- ufp_analysis.py             # Parse Cura .ufp files (print time, material, etc.)
|   |-- threemf_analysis.py         # Parse .3mf files (Bambu/OrcaSlicer, PrusaSlicer, Cura)
|   |-- stl_analysis.py             # STL file utilities
|   |-- database.py                 # MySQL connection pool wrapper
|   |-- config.py                   # Loads settings from environment variables
|   |-- requirements.txt            # Python dependencies
|   |-- Procfile                    # gunicorn start command for Railway
|   |-- nixpacks.toml               # Railway build config
|   |-- uploads/                    # Uploaded STL, UFP, 3MF & laser design files (UUID-named)
|   |-- .env                        # Local secrets (not committed)
|   |-- routes/
|   |   |-- pages.py                # HTML page routes (render_template)
|   |   |-- auth.py                 # /api/auth/* endpoints
|   |   |-- print_requests.py       # /api/print-requests/* endpoints (incl. upload-ufp, upload-3mf, upload-laser)
|   |   `-- admin.py                # /api/admin/* endpoints (production board, jobs, printers/equipment)
|   |-- jobs/
|   |   `-- cleanup.py              # Background job: auto-purge old uploaded files
|   `-- templates/                  # Jinja2 HTML templates
|       |-- base.html               # Layout, CSS, shared JS helpers (JWT, apiFetch)
|       |-- home.html               # Dashboard + embedded live production board (admin/staff)
|       |-- profile.html            # User profile: stats, print history, 2FA, change password
|       |-- print_requests.html     # Request list grouped by status (with service type badge)
|       |-- print_request_new.html  # Submit new print request (3D print or laser cut)
|       |-- print_request_detail.html       # Detail + STL viewer / laser options panel + admin actions
|       |-- print_request_detail_HEAD.html  # HEAD/staff detail view
|       |-- print_request_return.html       # Send-back feedback form
|       |-- production_board.html   # Standalone live production board
|       |-- printer_status.html     # Public-facing printer status page
|       |-- admin_students.html     # Admin: student management + search
|       |-- manage_printers.html    # Admin: equipment management (3D printers & laser cutters)
|       |-- manage_admins.html      # Admin: admin account management
|       |-- weekly_report.html      # Weekly report + CSV export
|       `-- registration/
|           |-- login.html          # Login page (@sandiego.edu enforced for students)
|           |-- signup.html         # Student registration (@sandiego.edu only)
|           `-- reset_password.html # Password reset (via email link)
|
`-- database/
    |-- schema.sql                  # Full database schema
    `-- migration_*.sql             # Incremental migrations (001-018)
```

---

## Architecture

```
Browser
  |
  | HTTPS  (Railway - single service)
  v
Flask (app.py)
  |-- Page routes  GET /  /login  /print-requests/*  /admin/*  etc.
  |     `-- render_template() -> Jinja2 HTML
  |
  `-- API routes   /api/*
        |-- auth_service.py    (register, login, JWT, 2FA)
        |-- print_service.py   (print request CRUD, stats)
        |-- email_service.py   (Gmail OAuth2)
        `-- MySQL (AWS RDS)
```

All pages and API endpoints are served from the same Flask process on the same domain — no proxy, no separate frontend service.

---

## URL Routes

| URL | Description |
|-----|-------------|
| `/` | Home / dashboard (includes embedded production board for admin/staff) |
| `/login` | Log in |
| `/signup` | Student registration |
| `/reset-password` | Password reset (token from email) |
| `/print-requests/` | Print request list |
| `/print-requests/new/` | Submit new request (3D print or laser cut) |
| `/print-requests/<id>/` | Request detail |
| `/print-requests/<id>/head/` | HEAD staff view |
| `/print-requests/<id>/return/` | Send-back feedback |
| `/admin/students/` | Student management |
| `/admin/printers/` | Equipment management (3D printers & laser cutters) |
| `/admin/admins/` | Admin account management |
| `/production/` | Standalone live production board |
| `/printers/` | Public printer status board |
| `/reports/weekly/` | Weekly report |
| `/profile/` | User profile |
| `/api/*` | REST API endpoints |

---

## User Roles

| Role | Description |
|------|-------------|
| `student` | Submit print/laser requests, track status |
| `student_staff` | Student with lab staff access (can manage production board) |
| `admin` | Review, approve, schedule, manage requests; full production board access |
| `professor` | View weekly reports |
| `manager` | View weekly reports + broader access |
| `super_admin` | Full access, can manage other admins |

---

## Local Development

### Prerequisites

- Python 3.11+
- MySQL 8.0 (or connection to AWS RDS)

### Setup

```bash
# Clone the repo
git clone https://github.com/chxjames/DGSpace-Project.git
cd DGSpace-Project

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
cd backend
pip install -r requirements.txt
```

### Environment Variables

Create `backend/.env`:

```env
DB_HOST=your-rds-host
DB_NAME=dgspace
DB_USER=your-db-user
DB_PASSWORD=your-db-password
DB_PORT=3306

JWT_SECRET_KEY=your-secret-key

GMAIL_CLIENT_ID=your-client-id
GMAIL_CLIENT_SECRET=your-client-secret
GMAIL_REFRESH_TOKEN=your-refresh-token
MAIL_DEFAULT_SENDER=your@gmail.com

UPLOAD_FOLDER=uploads
FLASK_ENV=development
FLASK_DEBUG=1
```

### Run

```bash
cd backend
python app.py
```

Visit `http://localhost:5000`

---

## Deployment (Railway)

- **Service**: `backend` (Root Directory: `/backend`)
- **Build**: nixpacks detects Python, installs from `requirements.txt`
- **Start**: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 300 --workers 1 --preload`
- **Auto-deploy**: pushes to `main` branch trigger a new build

### Environment Variables on Railway

Set the same variables as in `.env` above via Railway → Variables.

---

## Database Migrations

Migrations are in `database/migration_*.sql` and must be run manually against the RDS instance when deploying schema changes.

| Migration | Description |
|-----------|-------------|
| 001 | Initial print_requests table |
| 002 | STL upload support |
| 003 | Revision requested status |
| 004 | Professor/manager roles, senior design fields |
| 005 | UFP fields |
| 006 | Print logs, deadline field |
| 007 | Slicer fields |
| 008 | `student_staff` role |
| 009 | Printers table |
| 010 | Revision fields, TOTP + user type |
| 011 | Print jobs table |
| 012 | File deleted flag |
| 013 | Attempt number tracking |
| 014 | Print countdown support |
| 015 | Drop student email foreign key |
| 016 | `accepted_file_formats` column on `printers` table |
| 017 | *(reserved)* |
| 018 | `service_type` (`3dprint`/`laser`) and `laser_options` (JSON) on `print_requests` table |

> **Pending (run on production):**
> ```sql
> -- Migration 018
> ALTER TABLE print_requests
>   ADD COLUMN service_type VARCHAR(20) NOT NULL DEFAULT '3dprint',
>   ADD COLUMN laser_options TEXT NULL;
>
> -- Equipment type on printers table (no migration file yet)
> ALTER TABLE printers
>   ADD COLUMN device_type VARCHAR(20) NOT NULL DEFAULT '3dprint';
> ```

---

## Key Features

### Print Request Workflow
- **Status flow**: `pending` → `approved` → `queued` → `file_copied` → `printing` → `completed` / `failed`
- Students can delete their own pending/revision requests
- Retry logic: up to 3 attempts per request; auto-queues retry job on failure

### Service Types
- **3D Print** — STL file upload with Three.js in-browser 3D preview; UFP/3MF slice file upload
- **Laser Cut** — Design file upload (`.svg`, `.dxf`, `.pdf`, max 20 MB); material, job type (cut/engrave/both), and dimensions notes
- Service type badge (`🖨️ 3D` / `✂️ Laser`) shown on request list, production board RTS cards, and printer queue job cards

### File Parsing
- `.ufp` (Cura) — extracts print time, material weight, filament cost
- `.3mf` (Bambu Lab, OrcaSlicer, PrusaSlicer, Cura) — multi-slicer parser with G-code fallback
- File format badge shown on every RTS card in the production board

### Production Board
Standalone at `/production/` and embedded in the home page for admin/staff:
- **Service type filter** (All / 🖨️ 3D Print / ✂️ Laser Cut) on the Ready-to-Schedule list
- Equipment queue section automatically filters to show only 3D printers or laser cutters based on the active filter
- Drag-and-drop: assign RTS requests to equipment, move queued jobs between equipment
- Format-aware drag: incompatible printers shown in red and blocked during drag
- Live countdown timers per job with color-coded urgency (green → yellow → red → overdue)
- Browser push notifications when a print timer expires (only sent to the approving admin)
- Per-job assigner and approver name display

### Equipment Management (`/admin/printers/`)
- **Tab switcher**: 🖨️ 3D Printers / ✂️ Laser Cutters
- Per-printer accepted file formats (`.ufp`, `.3mf` for 3D; `.svg`, `.dxf`, `.pdf` for laser)
- Status management: Active / Maintenance / Retired
- Inline edit with format checkboxes

### Auth & Security
- TOTP 2FA — mandatory before accessing print requests
- Email verification on signup + password reset via Gmail API
- `@sandiego.edu` restriction — student registration and login restricted to university email

### Other
- **Weekly report** — per-student stats, CSV export
- **Admin invite email** — newly created admins receive credentials by email
- **Background cleanup** — auto-purges uploaded files for completed/cancelled requests after 2 weeks
- **Mobile responsive** layout


---

## Tech Stack

| Layer | Technology |
|---|---|
| Server | Python Flask 3.0 (pages + REST API, single service) |
| Templates | Jinja2 (served directly by Flask) |
| Database | MySQL 8.0 (AWS RDS) |
| Auth | JWT tokens + bcrypt + Email verification + TOTP 2FA |
| Email | Gmail API (OAuth2) |
| 3D Viewer | Three.js (STL preview in browser) |
| File Parsing | Custom parsers for Cura `.ufp` and multi-slicer `.3mf` slice data |
| Hosting | Railway (single service, auto-deploy on push to `main`) |

---

## Project Structure

```
DGSpace-Project/
|-- backend/                        # Flask application (single service)
|   |-- app.py                      # App factory, blueprint registration, background scheduler
|   |-- auth_service.py             # Register / login / JWT logic
|   |-- email_service.py            # Gmail API OAuth2 email sending
|   |-- print_service.py            # Print request CRUD + statistics
|   |-- totp_service.py             # 2FA (TOTP) - setup, verify, disable
|   |-- ufp_analysis.py             # Parse Cura .ufp files (print time, material, etc.)
|   |-- threemf_analysis.py         # Parse .3mf files (Bambu/OrcaSlicer, PrusaSlicer, Cura)
|   |-- stl_analysis.py             # STL file utilities
|   |-- database.py                 # MySQL connection pool wrapper
|   |-- config.py                   # Loads settings from environment variables
|   |-- requirements.txt            # Python dependencies
|   |-- Procfile                    # gunicorn start command for Railway
|   |-- nixpacks.toml               # Railway build config
|   |-- uploads/                    # Uploaded STL, UFP & 3MF files (UUID-named)
|   |-- .env                        # Local secrets (not committed)
|   |-- routes/
|   |   |-- pages.py                # HTML page routes (render_template)
|   |   |-- auth.py                 # /api/auth/* endpoints
|   |   |-- print_requests.py       # /api/print-requests/* endpoints (incl. upload-ufp, upload-3mf)
|   |   `-- admin.py                # /api/admin/* endpoints (production board, jobs, printers)
|   |-- jobs/
|   |   `-- cleanup.py              # Background job: auto-purge old uploaded files
|   `-- templates/                  # Jinja2 HTML templates
|       |-- base.html               # Layout, CSS, shared JS helpers (JWT, apiFetch)
|       |-- home.html               # Landing page + embedded live production board (admin/staff)
|       |-- profile.html            # User profile: stats, print history, 2FA, change password
|       |-- print_requests.html     # Request list grouped by status
|       |-- print_request_new.html  # Submit new print request
|       |-- print_request_detail.html       # Detail + Three.js STL viewer + admin actions
|       |-- print_request_detail_HEAD.html  # HEAD/staff detail view
|       |-- print_request_return.html       # Send-back feedback form
|       |-- production_board.html   # Standalone live production board
|       |-- printer_status.html     # Public-facing printer status page
|       |-- admin_students.html     # Admin: student management + search
|       |-- manage_printers.html    # Admin: printer management (incl. accepted file formats)
|       |-- manage_admins.html      # Admin: admin account management
|       |-- weekly_report.html      # Weekly report + CSV export
|       `-- registration/
|           |-- login.html          # Login page (@sandiego.edu enforced for students)
|           |-- signup.html         # Student registration (@sandiego.edu only)
|           `-- reset_password.html # Password reset (via email link)
|
`-- database/
    |-- schema.sql                  # Full database schema
    `-- migration_*.sql             # Incremental migrations (001-016)
```

---

## Architecture

```
Browser
  |
  | HTTPS  (Railway - single service)
  v
Flask (app.py)
  |-- Page routes  GET /  /login  /print-requests/*  /admin/*  etc.
  |     `-- render_template() -> Jinja2 HTML
  |
  `-- API routes   /api/*
        |-- auth_service.py    (register, login, JWT, 2FA)
        |-- print_service.py   (print request CRUD, stats)
        |-- email_service.py   (Gmail OAuth2)
        `-- MySQL (AWS RDS)
```

All pages and API endpoints are served from the same Flask process on the same domain - no proxy, no separate frontend service.

---

## URL Routes

| URL | Description |
|-----|-------------|
| `/` | Home / dashboard (includes embedded production board for admin/staff) |
| `/login` | Log in |
| `/signup` | Student registration |
| `/reset-password` | Password reset (token from email) |
| `/print-requests/` | Print request list |
| `/print-requests/new/` | Submit new request |
| `/print-requests/<id>/` | Request detail |
| `/print-requests/<id>/head/` | HEAD staff view |
| `/print-requests/<id>/return/` | Send-back feedback |
| `/admin/students/` | Student management |
| `/admin/printers/` | Printer management |
| `/admin/admins/` | Admin account management |
| `/production/` | Standalone live production board |
| `/printers/` | Public printer status board |
| `/reports/weekly/` | Weekly report |
| `/profile/` | User profile |
| `/api/*` | REST API endpoints |

---

## User Roles

| Role | Description |
|------|-------------|
| `student` | Submit print requests, track status |
| `student_staff` | Student with lab staff access (can manage production board) |
| `admin` | Review, approve, slice, manage prints; full production board access |
| `professor` | View weekly reports |
| `manager` | View weekly reports + broader access |
| `super_admin` | Full access, can manage other admins |

---

## Local Development

### Prerequisites

- Python 3.11+
- MySQL 8.0 (or connection to AWS RDS)

### Setup

```bash
# Clone the repo
git clone https://github.com/chxjames/DGSpace-Project.git
cd DGSpace-Project

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
cd backend
pip install -r requirements.txt
```

### Environment Variables

Create `backend/.env`:

```env
DB_HOST=your-rds-host
DB_NAME=dgspace
DB_USER=your-db-user
DB_PASSWORD=your-db-password
DB_PORT=3306

JWT_SECRET_KEY=your-secret-key

GMAIL_CLIENT_ID=your-client-id
GMAIL_CLIENT_SECRET=your-client-secret
GMAIL_REFRESH_TOKEN=your-refresh-token
MAIL_DEFAULT_SENDER=your@gmail.com

UPLOAD_FOLDER=uploads
FLASK_ENV=development
FLASK_DEBUG=1
```

### Run

```bash
cd backend
python app.py
```

Visit `http://localhost:5000`

---

## Deployment (Railway)

- **Service**: `backend` (Root Directory: `/backend`)
- **Build**: nixpacks detects Python, installs from `requirements.txt`
- **Start**: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 300 --workers 1 --preload`
- **Auto-deploy**: pushes to `main` branch trigger a new build

### Environment Variables on Railway

Set the same variables as in `.env` above via Railway -> Variables.

---

## Database Migrations

Migrations are in `database/migration_*.sql` and must be run manually against the RDS instance when deploying schema changes.

| Migration | Description |
|-----------|-------------|
| 001 | Initial print_requests table |
| 002 | STL upload support |
| 003 | Revision requested status |
| 004 | Professor/manager roles, senior design fields |
| 005 | UFP fields |
| 006 | Print logs, deadline field |
| 007 | Slicer fields |
| 008 | student_staff role |
| 009 | Printers table |
| 010 | Revision fields, TOTP + user type |
| 011 | Print jobs table |
| 012 | File deleted flag |
| 013 | Attempt number tracking |
| 014 | Print countdown support |
| 015 | Drop student email foreign key |
| 016 | `accepted_file_formats` column on `printers` table |

---

## Key Features

- **Print request workflow**: pending -> approved -> queued -> file copied -> printing -> completed/failed
- **STL file upload** with Three.js in-browser 3D preview
- **Multi-format slice file support**:
  - `.ufp` (Cura) - extracts print time, material weight, filament cost
  - `.3mf` (Bambu Lab, OrcaSlicer, PrusaSlicer, Cura) - multi-slicer parser with G-code fallback
  - File format badge shown on every RTS card in the production board
- **Per-printer file format settings** - each printer declares which formats it accepts (`.ufp`, `.3mf`, or both)
  - Production board filter dropdown to view printers by accepted format
  - Drag-and-drop blocked with visual feedback when file format is incompatible with target printer
- **TOTP 2FA** - mandatory before accessing print requests
- **Email verification** on signup + password reset via Gmail API
- **@sandiego.edu restriction** - student registration and login restricted to university email addresses
- **Production board** (standalone `/production/` and embedded in home page)
  - Drag-and-drop: assign RTS requests to printers, move queued jobs between printers
  - Format-aware drag: incompatible printers shown in red and blocked during drag
  - Live countdown timers per job with color-coded urgency (green -> yellow -> red -> overdue)
  - Browser push notifications when a print timer expires (only sent to the approving admin)
  - Per-job assigner and approver name display
  - Retry logic: up to 3 attempts per request, auto-queues retry jobs on failure
- **Weekly report** - per-student stats, CSV export
- **Admin invite email** - newly created admins receive credentials by email
- **Background cleanup** - auto-purges uploaded files for completed/cancelled requests after 2 weeks
- **Mobile responsive** layout
