# DGSpace — 3D Print Request Management System

A full-stack web application for **Donald's Garage** at the University of San Diego. Students submit 3D print requests and admins review, slice, and manage them through a streamlined production workflow.

**Live:** https://dgspace-project-production.up.railway.app

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
| UFP Parsing | Custom parser for Cura `.ufp` slice data |
| Hosting | Railway (single service, auto-deploy on push to `main`) |

---

## Project Structure

```
DGSpace-Project/
├── backend/                        # Flask application (single service)
│   ├── app.py                      # App factory, blueprint registration, background scheduler
│   ├── auth_service.py             # Register / login / JWT logic
│   ├── email_service.py            # Gmail API OAuth2 email sending
│   ├── print_service.py            # Print request CRUD + statistics
│   ├── totp_service.py             # 2FA (TOTP) — setup, verify, disable
│   ├── ufp_analysis.py             # Parse Cura .ufp files (print time, material, etc.)
│   ├── stl_analysis.py             # STL file utilities
│   ├── database.py                 # MySQL connection pool wrapper
│   ├── config.py                   # Loads settings from environment variables
│   ├── requirements.txt            # Python dependencies
│   ├── Procfile                    # gunicorn start command for Railway
│   ├── nixpacks.toml               # Railway build config
│   ├── uploads/                    # Uploaded STL & UFP files (UUID-named)
│   ├── .env                        # Local secrets (not committed)
│   ├── routes/
│   │   ├── pages.py                # HTML page routes (render_template)
│   │   ├── auth.py                 # /api/auth/* endpoints
│   │   ├── print_requests.py       # /api/print-requests/* endpoints
│   │   └── admin.py                # /api/admin/* endpoints (production board, jobs, printers)
│   ├── jobs/
│   │   └── cleanup.py              # Background job: auto-purge old uploaded files
│   └── templates/                  # Jinja2 HTML templates
│       ├── base.html               # Layout, CSS, shared JS helpers (JWT, apiFetch)
│       ├── home.html               # Landing page + embedded live production board (admin/staff)
│       ├── profile.html            # User profile: stats, print history, 2FA, change password
│       ├── print_requests.html     # Request list grouped by status
│       ├── print_request_new.html  # Submit new print request
│       ├── print_request_detail.html       # Detail + Three.js STL viewer + admin actions
│       ├── print_request_detail_HEAD.html  # HEAD/staff detail view
│       ├── print_request_return.html       # Send-back feedback form
│       ├── production_board.html   # Standalone live production board
│       ├── printer_status.html     # Public-facing printer status page
│       ├── admin_students.html     # Admin: student management + search
│       ├── manage_printers.html    # Admin: printer management
│       ├── manage_admins.html      # Admin: admin account management
│       ├── weekly_report.html      # Weekly report + CSV export
│       └── registration/
│           ├── login.html          # Login page
│           ├── signup.html         # Student registration + email verification
│           └── reset_password.html # Password reset (via email link)
│
└── database/
    ├── schema.sql                  # Full database schema
    └── migration_*.sql             # Incremental migrations (001–015)
```

---

## Architecture

```
Browser
  │
  │ HTTPS  (Railway — single service)
  ▼
Flask (app.py)
  ├── Page routes  GET /  /login  /print-requests/*  /admin/*  etc.
  │     └── render_template() → Jinja2 HTML
  │
  └── API routes   /api/*
        ├── auth_service.py    (register, login, JWT, 2FA)
        ├── print_service.py   (print request CRUD, stats)
        ├── email_service.py   (Gmail OAuth2)
        └── MySQL (AWS RDS)
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

Set the same variables as in `.env` above via Railway → Variables.

---

## Key Features

- **Print request workflow**: pending → approved → queued → file copied → printing → completed/failed
- **STL file upload** with Three.js in-browser 3D preview
- **UFP file parsing** — extracts print time, material weight, filament cost from Cura slice files
- **TOTP 2FA** — mandatory before accessing print requests
- **Email verification** on signup + password reset via Gmail API
- **Production board** (standalone `/production/` and embedded in home page)
  - Drag-and-drop: assign RTS requests to printers, move queued jobs between printers
  - Live countdown timers per job with color-coded urgency (green → yellow → red → overdue)
  - Browser push notifications when a print timer expires (only sent to the approving admin)
  - Per-job assigner and approver name display
  - Retry logic: up to 3 attempts per request, auto-queues retry jobs on failure
- **Weekly report** — per-student stats, CSV export
- **Admin invite email** — newly created admins receive credentials by email
- **Background cleanup** — auto-purges uploaded files for completed/cancelled requests after 2 weeks
- **Mobile responsive** layout

