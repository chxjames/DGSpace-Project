# DGSpace - Print & Laser Cut Request Management System

A full-stack web application for **Donald's Garage** at the University of San Diego. Students submit 3D print and laser cutting requests, and admins review, schedule, and manage them through a streamlined production workflow.

**Live:** <https://dgspace-project-production.up.railway.app>

---

## Tech Stack

| Layer        | Technology                                                                        |
| ------------ | --------------------------------------------------------------------------------- |
| Server       | Python Flask 3.0 (pages + REST API, single service)                               |
| Templates    | Jinja2 (served directly by Flask)                                                 |
| Database     | MySQL 8.0 (AWS RDS)                                                               |
| Auth         | JWT tokens + bcrypt + Email verification + TOTP 2FA                               |
| Email        | Gmail API (OAuth2)                                                                |
| 3D Viewer    | Three.js (STL preview in browser)                                                 |
| File Parsing | Custom parsers for Cura `.ufp`, multi-slicer `.3mf`, G-code / `.nc`, and DXF/SVG |
| DXF Preview  | ezdxf 1.3.4 — renders DXF to inline SVG in the browser                            |
| Hosting      | Railway (single service, auto-deploy on push to `main`)                           |

---

## Project Structure

```
DGSpace-Project/
|-- backend/                        # Flask application (single service)
|   |-- app.py                      # App factory, blueprint registration, background scheduler
|   |-- auth_service.py             # Register / login / JWT logic
|   |-- email_service.py            # Gmail API OAuth2 email sending (service-type aware)
|   |-- print_service.py            # Print request CRUD + statistics
|   |-- totp_service.py             # 2FA (TOTP) - setup, verify, disable
|   |-- ufp_analysis.py             # Parse Cura .ufp files (print time, material, etc.)
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
|   |   |-- print_requests.py       # /api/print-requests/* endpoints
|   |   |                           #   incl. upload-ufp, upload-3mf, upload-laser,
|   |   |                           #         upload-gcode, preview-design (SVG/DXF/PDF)
|   |   `-- admin.py                # /api/admin/* endpoints (production board, jobs, printers)
|   |-- jobs/
|   |   `-- cleanup.py              # Background job: auto-purge old uploaded files
|   `-- templates/                  # Jinja2 HTML templates
|       |-- base.html               # Layout, CSS, shared JS helpers (JWT, apiFetch)
|       |-- home.html               # Dashboard + embedded live production board (admin/staff)
|       |-- profile.html            # User profile: stats, print history, 2FA, change password
|       |-- print_requests.html     # Request list grouped by status (service type badge)
|       |-- print_request_new.html  # Submit new request (3D print or laser cut)
|       |-- print_request_detail.html       # Detail + STL viewer / laser panel + admin actions
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
    `-- migration_*.sql             # Incremental migrations (001-015+)
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
        |-- email_service.py   (Gmail OAuth2 -- adapts content for 3D print vs laser cut)
        `-- MySQL (AWS RDS)
```

All pages and API endpoints are served from the same Flask process on the same domain — no proxy, no separate frontend service.

---

## URL Routes

| URL                            | Description                                                           |
| ------------------------------ | --------------------------------------------------------------------- |
| `/`                            | Home / dashboard (includes embedded production board for admin/staff) |
| `/login`                       | Log in                                                                |
| `/signup`                      | Student registration                                                  |
| `/reset-password`              | Password reset (token from email)                                     |
| `/print-requests/`             | Print request list                                                    |
| `/print-requests/new/`         | Submit new request (3D print or laser cut)                            |
| `/print-requests/<id>/`        | Request detail                                                        |
| `/print-requests/<id>/head/`   | HEAD/staff view                                                       |
| `/print-requests/<id>/return/` | Send-back feedback                                                    |
| `/admin/students/`             | Student management                                                    |
| `/admin/printers/`             | Equipment management (3D printers & laser cutters)                    |
| `/admin/admins/`               | Admin account management                                              |
| `/production/`                 | Standalone live production board                                      |
| `/printers/`                   | Public printer status board                                           |
| `/reports/weekly/`             | Weekly report                                                         |
| `/profile/`                    | User profile                                                          |
| `/api/*`                       | REST API endpoints                                                    |

---

## User Roles

| Role            | Description                                                              |
| --------------- | ------------------------------------------------------------------------ |
| `student`       | Submit print/laser requests, track status                                |
| `student_staff` | Student with lab staff access (can manage production board)              |
| `admin`         | Review, approve, schedule, manage requests; full production board access |

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

| Migration | Description                                                                             |
| --------- | --------------------------------------------------------------------------------------- |
| 001       | Initial print_requests table                                                            |
| 002       | STL upload support                                                                      |
| 003       | Revision requested status                                                               |
| 004       | Professor/manager roles, senior design fields                                           |
| 005       | UFP fields                                                                              |
| 006       | Print logs, deadline field                                                              |
| 007       | Slicer fields                                                                           |
| 008       | `student_staff` role                                                                    |
| 009       | Printers table                                                                          |
| 010       | Revision fields, TOTP + user type                                                       |
| 011       | Print jobs table                                                                        |
| 012       | File deleted flag                                                                       |
| 013       | Attempt number tracking                                                                 |
| 014       | Print countdown support                                                                 |
| 015       | Drop student email foreign key                                                          |

> **Schema additions applied directly (no migration file):**
>
> ```sql
> -- Laser cut support on print_requests
> ALTER TABLE print_requests
>   ADD COLUMN service_type  VARCHAR(20) NOT NULL DEFAULT '3dprint',
>   ADD COLUMN laser_options TEXT NULL;
>
> -- Equipment type on printers
> ALTER TABLE printers
>   ADD COLUMN device_type VARCHAR(20) NOT NULL DEFAULT '3dprint';
>
> -- Accepted file formats per printer (e.g. 'ufp,3mf' or 'svg,dxf,pdf')
> ALTER TABLE printers
>   ADD COLUMN accepted_file_formats VARCHAR(200) NULL;
> ```

---

## Key Features

### Print Request Workflow

- **Status flow**: `pending` → `approved` → `queued` → `file_transferred` → `printing` → `completed` / `failed`
- Students can delete their own pending / revision-requested requests
- Retry logic: up to 3 attempts per request; auto-queues a retry job on failure
- Completion email automatically adapts subject, header, and body for **3D print** vs **laser cut** jobs

### Service Types

| Type | Badge | File types | Admin review |
|---|---|---|---|
| 3D Print | 🖨️ 3D | `.stl`, `.ufp`, `.3mf` | UFP/3MF slice file upload, auto-parsed print time & material |
| Laser Cut | ✂️ Laser | `.svg`, `.dxf`, `.pdf` (design) + `.gcode` / `.nc` (toolpath) | Design file upload + G-code upload with estimated cut time |

Service type badge shown on: request list, detail page, production board RTS cards, and printer queue job cards.

### File Parsing

| File | Parser | Extracted data |
|---|---|---|
| `.ufp` (Cura) | `ufp_analysis.py` | Print time, material weight, filament cost |
| `.3mf` (Bambu, OrcaSlicer, PrusaSlicer, Cura) | inline in `print_requests.py` | Print time, material, slicer version |
| `.gcode` / `.nc` | `_parse_gcode_time()` in `print_requests.py` | Estimated cut time — supports LightBurn, Snapmaker Luban (`estimated_time(s):`), and Fusion 360 comment formats |
| `.dxf` | ezdxf (server-side render) | Converted to SVG via `SVGBackend` with explicit `Page(420, 297)` + `Settings(fit_page=True)` to handle files with no paper size |
| `.svg` | served directly | Browser preview |
| `.pdf` | served directly | Browser preview via `<embed>` |

### Design File Preview

A preview modal on the laser cut request detail page supports:

- **SVG** — served directly, displayed inline
- **DXF** — converted server-side to SVG using `ezdxf 1.3.4`; an explicit A3 page layout is passed to `backend.get_string()` so files with no paper dimensions always render correctly
- **PDF** — displayed via browser `<embed>`

### Laser Cut Admin Workflow

1. **Step 1 — Review design**: admin previews the uploaded design file (SVG/DXF/PDF) in-browser
2. **Step 2 — Upload G-code**: admin uploads a prepared `.gcode` or `.nc` toolpath file
   - Cut time is auto-parsed (LightBurn, Snapmaker Luban, Fusion 360 formats)
   - Parsed cut time is shown on the approval card
3. **Approve**: cut time is stored in `ufp_print_time_minutes` and drives the production board countdown

### Production Board

Standalone at `/production/` and embedded in the home page for admin/staff:

- **Service type filter** — All / 🖨️ 3D Print / ✂️ Laser Cut on the Ready-to-Schedule list; equipment section shows only the matching type
- **Separate queues** — 🖨️ 3D Printer Queues and ✂️ Laser Cutter Queues rendered independently with correct format badges
- **Drag-and-drop assignment** — drag an RTS card onto any equipment queue
  - **Service-type aware**: laser requests only highlight laser cutters green; 3D print requests only highlight compatible 3D printers; mismatches shown in red and blocked
  - **Format-aware**: within 3D printers, incompatible file formats are also blocked
- **Empty queue → immediate start**: assigning to an empty queue sends `estimated_start: null` — no countdown shown, staff can proceed directly to File Copied
- **Auto time-chaining**: assigning to a non-empty queue calculates `estimated_start` / `estimated_end` by chaining off the queue's latest end time — no manual entry needed
- **Live countdown timers** per printing job: 🟢 > 30 min / 🟡 10–30 min / 🔴 < 10 min / overdue
- **Queued job scheduling**: next queued job shows a live "starts in …" countdown; later jobs show static scheduled date/time
- After any status change or job removal, remaining queued jobs are auto-rescheduled in sequence via `POST /api/admin/jobs/reschedule`
- **Browser push notifications** when a print/cut timer expires (only sent to the approving admin)
- Per-job assigner and approver name display

### Assign Modal — Printer Dropdown Filtering

The "Assign to Printer" modal only lists equipment **compatible with the selected request**:

- Laser cut request → only active laser cutters
- 3D print request → only active 3D printers whose `accepted_file_formats` includes the uploaded file type
- If no compatible equipment is active, displays a descriptive message (e.g. "— No compatible active laser cutters —")

### Equipment Management (`/admin/printers/`)

- **Tab switcher**: 🖨️ 3D Printers / ✂️ Laser Cutters (filtered by `device_type`)
- Per-printer accepted file formats (`.ufp`, `.3mf` for 3D; `.svg`, `.dxf`, `.pdf` for laser)
- Status management: Active / Maintenance / Retired
- Inline edit with format checkboxes

### Auth & Security

- TOTP 2FA — mandatory before accessing print requests
- Email verification on signup + password reset via Gmail API
- `@sandiego.edu` restriction — student registration and login restricted to university email

### Notifications & Email

| Trigger | Recipient | Content |
|---|---|---|
| Request completed (3D print) | Student | Subject: "Your 3D Print is Ready"; body mentions print pickup |
| Request completed (laser cut) | Student | Subject: "Your Laser Cut is Ready"; body mentions cut pickup |
| Admin invite | New admin | Login credentials by email |
| Print/cut timer expires | Approving admin | Browser push notification |

### Other

- **Weekly report** — per-student stats, CSV export
- **Background cleanup** — auto-purges uploaded files for completed/cancelled requests after 2 weeks
- **Mobile responsive** layout
