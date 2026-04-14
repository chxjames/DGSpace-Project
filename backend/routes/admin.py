import bcrypt
import datetime
import jwt as _jwt
from flask import Blueprint, request, jsonify
from database import db
from auth_service import AuthService
from email_service import EmailService
from print_service import PrintService
from totp_service import TotpService
from config import Config

admin_bp = Blueprint('admin', __name__)


# ── Auth helper ───────────────────────────────────────────────────────────────

def _get_auth_payload(require_type=None):
    """Parse the JWT payload from the Authorization header. Optionally validates user_type."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload:
        return None
    if require_type and payload.get('user_type') != require_type:
        return None
    return payload


# ==================== ADMIN USER MANAGEMENT ====================

@admin_bp.route('/api/admin/students', methods=['GET'])
def admin_list_students():
    """List all student accounts (Admin only)."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    students = db.fetch_all(
        """
        SELECT email, full_name, department, role, email_verified, created_at, last_login
        FROM students
        ORDER BY created_at DESC
        """
    ) or []

    return jsonify({'success': True, 'students': students}), 200


@admin_bp.route('/api/admin/students/<email>', methods=['DELETE'])
def admin_delete_student(email: str):
    """Delete a student account (Admin only)."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    if not email or '@' not in email:
        return jsonify({'success': False, 'message': 'Invalid email'}), 400

    existing = db.fetch_one("SELECT email FROM students WHERE email = %s", (email,))
    if not existing:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    db.execute_query("DELETE FROM totp_secrets WHERE email = %s AND user_type = 'student'", (email,))
    db.execute_query("DELETE FROM password_reset_tokens WHERE email = %s AND user_type = 'student'", (email,))
    db.execute_query("DELETE FROM email_verification_codes WHERE email = %s AND user_type = 'student'", (email,))

    delete_result = db.execute_query("DELETE FROM students WHERE email = %s", (email,))
    if delete_result is None:
        return jsonify({'success': False, 'message': 'Failed to delete student'}), 500

    return jsonify({'success': True, 'message': 'Student deleted'}), 200


@admin_bp.route('/api/admin/students/<email>/role', methods=['PATCH'])
def admin_update_student_role(email: str):
    """Promote or demote a student to/from student_staff (Admin only)."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    data = request.json or {}
    new_role = data.get('role', '').strip()
    if new_role not in ('student', 'student_staff'):
        return jsonify({'success': False, 'message': "role must be 'student' or 'student_staff'"}), 400

    existing = db.fetch_one("SELECT email FROM students WHERE email = %s", (email,))
    if not existing:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    db.execute_query("UPDATE students SET role = %s WHERE email = %s", (new_role, email))
    return jsonify({'success': True, 'message': f'Role updated to {new_role}', 'role': new_role}), 200


# ==================== PRODUCTION BOARD ====================

@admin_bp.route('/api/admin/production-board', methods=['GET'])
def get_production_board():
    """
    Return everything needed for the Production Board in one call.
    Access: admin or student_staff.
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    payload = AuthService.verify_jwt_token(auth_header.split(' ')[1])
    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    ready = db.fetch_all("""
        SELECT
            pr.request_id   AS id,
            pr.project_name,
            pr.student_email,
            s.full_name      AS student_name,
            pr.material_type,
            pr.color_preference,
            pr.priority,
            pr.deadline_date,
            pr.ufp_print_time_minutes,
            pr.ufp_material_g,
            pr.ufp_file_path,
            pr.ufp_original_name,
            pr.status,
            pr.created_at
        FROM print_requests pr
        LEFT JOIN students s ON s.email = pr.student_email
        WHERE pr.status = 'approved'
          AND pr.ufp_file_path IS NOT NULL
          AND pr.file_deleted  = 0
          AND NOT EXISTS (
              SELECT 1 FROM print_jobs pj
              WHERE pj.request_id = pr.request_id
                AND pj.status NOT IN ('cancelled', 'failed')
          )
        ORDER BY
            FIELD(pr.priority, 'urgent', 'high', 'normal', 'low'),
            pr.deadline_date ASC,
            pr.created_at   ASC
    """) or []

    printers = db.fetch_all(
        "SELECT printer_id, printer_name, model, location, status, notes FROM printers ORDER BY printer_name"
    ) or []

    for p in printers:
        jobs = db.fetch_all("""
            SELECT
                pj.job_id,
                pj.request_id,
                pj.queue_position,
                pj.status          AS job_status,
                pj.attempt_number,
                pj.assigned_by,
                pj.assigned_at,
                pj.estimated_start,
                pj.estimated_end,
                pj.started_at,
                COALESCE(
                    pj.print_end_expected,
                    CASE WHEN pj.status = 'printing' AND pj.started_at IS NOT NULL
                         THEN DATE_ADD(pj.started_at, INTERVAL pr.ufp_print_time_minutes MINUTE)
                         ELSE NULL END
                )                  AS print_end_expected,
                pj.completed_at,
                pj.notes           AS job_notes,
                pr.project_name,
                pr.student_email,
                pr.reviewed_by,
                s.full_name        AS student_name,
                pr.material_type,
                pr.priority,
                pr.deadline_date,
                pr.ufp_print_time_minutes,
                pr.ufp_material_g
            FROM print_jobs pj
            JOIN print_requests pr ON pr.request_id = pj.request_id
            LEFT JOIN students s   ON s.email = pr.student_email
            WHERE pj.printer_id = %s
              AND pj.status NOT IN ('completed', 'cancelled', 'failed')
            ORDER BY pj.queue_position ASC
        """, (p['printer_id'],)) or []
        p['queue'] = jobs

    return jsonify({
        'success': True,
        'ready_to_schedule': ready,
        'printers': printers
    }), 200


@admin_bp.route('/api/printers/status', methods=['GET'])
def get_printer_status():
    """
    Student-facing printer status summary.
    Returns a sanitised per-printer view — no student names, no job details.
    Access: any authenticated user (student, admin, student_staff).
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    payload = AuthService.verify_jwt_token(auth_header.split(' ')[1])
    if not payload:
        return jsonify({'success': False, 'message': 'Invalid token'}), 403

    now = datetime.datetime.utcnow()

    printers = db.fetch_all(
        "SELECT printer_id, printer_name, model, location, status FROM printers ORDER BY printer_name"
    ) or []

    result = []
    for p in printers:
        # Active (non-terminal) jobs for this printer
        jobs = db.fetch_all("""
            SELECT
                pj.status AS job_status,
                COALESCE(
                    pj.print_end_expected,
                    CASE WHEN pj.status = 'printing' AND pj.started_at IS NOT NULL
                         THEN DATE_ADD(pj.started_at, INTERVAL pr.ufp_print_time_minutes MINUTE)
                         ELSE NULL END
                ) AS print_end_expected
            FROM print_jobs pj
            JOIN print_requests pr ON pr.request_id = pj.request_id
            WHERE pj.printer_id = %s
              AND pj.status NOT IN ('completed', 'cancelled', 'failed')
            ORDER BY pj.queue_position ASC
        """, (p['printer_id'],)) or []

        printing_job = next((j for j in jobs if j['job_status'] == 'printing'), None)
        queued_count = sum(1 for j in jobs if j['job_status'] in ('queued', 'file_transferred'))

        # Minutes remaining for the active printing job
        minutes_remaining = None
        print_end_expected = None
        if printing_job and printing_job.get('print_end_expected'):
            end_dt = printing_job['print_end_expected']
            if isinstance(end_dt, str):
                end_dt = datetime.datetime.fromisoformat(end_dt)
            diff_sec = (end_dt - now).total_seconds()
            minutes_remaining = max(0, int(diff_sec / 60))
            print_end_expected = end_dt.isoformat()

        # Derive a simple display state
        printer_hw_status = p['status']  # 'active', 'inactive', 'maintenance'
        if printer_hw_status in ('inactive', 'maintenance'):
            display_state = 'offline'
        elif printing_job:
            display_state = 'printing'
        elif queued_count > 0:
            display_state = 'busy'
        else:
            display_state = 'idle'

        result.append({
            'printer_id':         p['printer_id'],
            'printer_name':       p['printer_name'],
            'model':              p['model'] or '',
            'location':           p['location'] or '',
            'hw_status':          printer_hw_status,
            'display_state':      display_state,      # 'printing'|'busy'|'idle'|'offline'
            'queued_count':       queued_count,
            'minutes_remaining':  minutes_remaining,  # None if not printing
            'print_end_expected': print_end_expected, # ISO string UTC, or None
        })

    return jsonify({'success': True, 'printers': result}), 200


@admin_bp.route('/api/admin/print-requests/<int:request_id>/assign', methods=['POST'])
def assign_to_printer(request_id):
    """
    Assign an approved request to a printer queue.
    Body: { printer_id, estimated_start?, estimated_end?, notes? }
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    payload = AuthService.verify_jwt_token(auth_header.split(' ')[1])
    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    data = request.json or {}
    printer_id = data.get('printer_id')
    if not printer_id:
        return jsonify({'success': False, 'message': 'printer_id is required'}), 400

    req = db.fetch_one(
        "SELECT request_id, status, ufp_file_path FROM print_requests WHERE request_id = %s",
        (request_id,)
    )
    if not req:
        return jsonify({'success': False, 'message': 'Request not found'}), 404
    if req['status'] not in ('approved',):
        return jsonify({'success': False, 'message': f'Request must be in "approved" state (currently "{req["status"]}")'}), 409
    if not req['ufp_file_path']:
        return jsonify({'success': False, 'message': 'Request has no UFP file — cannot schedule'}), 409

    printer = db.fetch_one("SELECT printer_id, status FROM printers WHERE printer_id = %s", (printer_id,))
    if not printer:
        return jsonify({'success': False, 'message': 'Printer not found'}), 404
    if printer['status'] != 'active':
        return jsonify({'success': False, 'message': f'Printer is not active (status: {printer["status"]})'}), 409

    existing_job = db.fetch_one(
        "SELECT job_id FROM print_jobs WHERE request_id = %s AND status NOT IN ('cancelled','failed')",
        (request_id,)
    )
    if existing_job:
        return jsonify({'success': False, 'message': 'This request already has an active print job'}), 409

    pos_row = db.fetch_one(
        "SELECT COALESCE(MAX(queue_position), 0) + 1 AS next_pos FROM print_jobs WHERE printer_id = %s AND status NOT IN ('completed','cancelled','failed')",
        (printer_id,)
    )
    next_pos = pos_row['next_pos'] if pos_row else 1

    estimated_start = data.get('estimated_start') or None
    estimated_end   = data.get('estimated_end')   or None
    notes           = (data.get('notes') or '').strip() or None

    job_id = db.execute_query(
        """INSERT INTO print_jobs
           (request_id, printer_id, queue_position, status, assigned_by, estimated_start, estimated_end, notes)
           VALUES (%s, %s, %s, 'queued', %s, %s, %s, %s)""",
        (request_id, printer_id, next_pos, payload['email'], estimated_start, estimated_end, notes)
    )

    db.execute_query(
        "UPDATE print_requests SET status = 'queued' WHERE request_id = %s",
        (request_id,)
    )

    return jsonify({
        'success': True,
        'message': 'Request assigned to printer queue',
        'job_id': job_id,
        'queue_position': next_pos
    }), 201


@admin_bp.route('/api/admin/jobs/<int:job_id>/status', methods=['PATCH'])
def update_job_status(job_id):
    """
    Advance a print job through its lifecycle.
    Body: { status: 'file_transferred'|'printing'|'completed'|'failed'|'cancelled', notes? }

    Special behaviour on 'failed':
      - Attempt 1 or 2 → mark job failed, create a new job (attempt+1) on same printer.
      - Attempt 3 → mark job failed, send request back to student with auto feedback.
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    payload = AuthService.verify_jwt_token(auth_header.split(' ')[1])
    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    data       = request.json or {}
    new_status = (data.get('status') or '').strip()
    valid = ('file_transferred', 'printing', 'completed', 'failed', 'cancelled')
    if new_status not in valid:
        return jsonify({'success': False, 'message': f'Invalid status. Must be one of: {", ".join(valid)}'}), 400

    job = db.fetch_one(
        "SELECT job_id, request_id, printer_id, status, attempt_number FROM print_jobs WHERE job_id = %s",
        (job_id,)
    )
    if not job:
        return jsonify({'success': False, 'message': 'Job not found'}), 404

    # Guard: only one job can be printing per printer
    if new_status == 'printing':
        already = db.fetch_one(
            "SELECT job_id FROM print_jobs "
            "WHERE printer_id = %s AND status = 'printing' AND job_id != %s",
            (job['printer_id'], job_id)
        )
        if already:
            return jsonify({
                'success': False,
                'message': 'Another job is already printing on this printer. Finish or fail that job first.'
            }), 400

    notes = (data.get('notes') or '').strip() or None

    if new_status == 'printing':
        req_row = db.fetch_one(
            "SELECT pr.ufp_print_time_minutes FROM print_requests pr "
            "JOIN print_jobs pj ON pj.request_id = pr.request_id "
            "WHERE pj.job_id = %s", (job_id,)
        )
        mins = (req_row or {}).get('ufp_print_time_minutes') or 0
        note_part = ', notes = %s' if notes else ''
        params = (new_status,) + ((notes,) if notes else ()) + (mins, job_id)
        db.execute_query(
            f"UPDATE print_jobs SET status = %s {note_part}, "
            f"started_at = NOW(), "
            f"print_end_expected = DATE_ADD(NOW(), INTERVAL %s MINUTE), "
            f"staff_notified = 0 "
            f"WHERE job_id = %s",
            params
        )
    elif new_status in ('completed', 'failed', 'cancelled'):
        note_part = ', notes = %s' if notes else ''
        params = (new_status,) + ((notes,) if notes else ()) + (job_id,)
        db.execute_query(
            f"UPDATE print_jobs SET status = %s {note_part}, completed_at = NOW() WHERE job_id = %s",
            params
        )
    else:
        note_part = ', notes = %s' if notes else ''
        params = (new_status,) + ((notes,) if notes else ()) + (job_id,)
        db.execute_query(
            f"UPDATE print_jobs SET status = %s {note_part} WHERE job_id = %s",
            params
        )

    # Failed: retry or send back
    if new_status == 'failed':
        attempt = job.get('attempt_number') or 1
        MAX_ATTEMPTS = 3

        if attempt < MAX_ATTEMPTS:
            next_attempt = attempt + 1
            pos_row = db.fetch_one(
                "SELECT COALESCE(MAX(queue_position), 0) + 1 AS next_pos FROM print_jobs "
                "WHERE printer_id = %s AND status NOT IN ('completed','cancelled','failed')",
                (job['printer_id'],)
            )
            next_pos = pos_row['next_pos'] if pos_row else 1
            db.execute_query(
                """INSERT INTO print_jobs
                   (request_id, printer_id, queue_position, status, assigned_by, attempt_number)
                   VALUES (%s, %s, %s, 'queued', %s, %s)""",
                (job['request_id'], job['printer_id'], next_pos, payload['email'], next_attempt)
            )
            db.execute_query(
                "UPDATE print_requests SET status = 'queued' WHERE request_id = %s",
                (job['request_id'],)
            )
            return jsonify({
                'success': True,
                'message': f'Attempt {attempt} failed. Retry #{next_attempt - 1} queued automatically.',
                'retry': True,
                'attempt': next_attempt,
                'attempts_remaining': MAX_ATTEMPTS - next_attempt
            }), 200
        else:
            auto_note = (
                f"Your print failed after {MAX_ATTEMPTS} attempts. "
                "Please review your model for printability issues "
                "(overhangs, thin walls, supports, etc.) and resubmit."
            )
            db.execute_query(
                """UPDATE print_requests
                   SET status = 'revision_requested',
                       admin_notes = %s,
                       unlocked_fields = NULL
                   WHERE request_id = %s""",
                (auto_note, job['request_id'])
            )
            return jsonify({
                'success': True,
                'message': f'All {MAX_ATTEMPTS} attempts failed. Request sent back to student for revision.',
                'retry': False,
                'sent_back': True
            }), 200

    # All other statuses: mirror to print_requests
    req_status_map = {
        'file_transferred': 'queued',
        'printing':         'printing',
        'completed':        'completed',
        'cancelled':        'approved',
    }
    db.execute_query(
        "UPDATE print_requests SET status = %s WHERE request_id = %s",
        (req_status_map[new_status], job['request_id'])
    )

    # Notify student on completion
    if new_status == 'completed':
        db.execute_query(
            "UPDATE print_requests SET completed_at = NOW() WHERE request_id = %s",
            (job['request_id'],)
        )
        student_row = db.fetch_one(
            """SELECT pr.student_email, pr.project_name, s.full_name
               FROM print_requests pr
               LEFT JOIN students s ON pr.student_email = s.email
               WHERE pr.request_id = %s""",
            (job['request_id'],)
        )
        if student_row and student_row.get('student_email'):
            EmailService.send_print_completed_email(
                to_email=student_row['student_email'],
                full_name=student_row.get('full_name') or student_row['student_email'],
                project_name=student_row.get('project_name') or 'Your project',
                request_id=job['request_id'],
            )

    return jsonify({'success': True, 'message': f'Job status updated to "{new_status}"'}), 200


# ── Operating-hours helper ────────────────────────────────────────────────────
# Mon=0 10:00-16:00, Tue-Thu=1-3 09:00-17:00, Fri=4 09:00-16:00
_OP_HOURS = {
    0: (10, 16),
    1: ( 9, 17),
    2: ( 9, 17),
    3: ( 9, 17),
    4: ( 9, 16),
}

def _within_op_hours(dt):
    """Return True if dt (datetime) falls inside operating hours."""
    wd = dt.weekday()
    if wd not in _OP_HOURS:
        return False
    open_h, close_h = _OP_HOURS[wd]
    return open_h <= dt.hour < close_h

def _job_exceeds_hours(print_end_dt):
    """Return True if print_end_dt is outside operating hours (job will overrun)."""
    wd = print_end_dt.weekday()
    if wd not in _OP_HOURS:
        return True
    _, close_h = _OP_HOURS[wd]
    closing = print_end_dt.replace(hour=close_h, minute=0, second=0, microsecond=0)
    return print_end_dt > closing


@admin_bp.route('/api/admin/jobs/<int:job_id>/mark-notified', methods=['POST'])
def mark_job_notified(job_id):
    """Mark a job's staff_notified flag as 1 so pollNotifications won't re-fire it.
    Called by the client-side tickCountdowns when it fires a notification."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False}), 401
    payload = AuthService.verify_jwt_token(auth_header.split(' ')[1])
    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False}), 403

    current_email = payload['email']
    # Only allow the assigned staff member to mark it (prevents spoofing)
    db.execute_update(
        "UPDATE print_jobs SET staff_notified = 1 "
        "WHERE job_id = %s AND assigned_by = %s AND staff_notified = 0",
        (job_id, current_email)
    )
    return jsonify({'success': True}), 200


@admin_bp.route('/api/admin/notifications', methods=['GET'])
def get_staff_notifications():
    """Poll endpoint — returns pending notifications for the logged-in staff member."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'notifications': []}), 401
    payload = AuthService.verify_jwt_token(auth_header.split(' ')[1])
    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False, 'notifications': []}), 403

    now = datetime.datetime.utcnow()

    # Only notify the staff member who originally assigned this job.
    # Use an atomic UPDATE...WHERE staff_notified=0 to claim the notification
    # and avoid race conditions where multiple staff members poll simultaneously.
    current_email = payload['email']

    candidate_jobs = db.fetch_all("""
        SELECT pj.job_id, pj.print_end_expected,
               pr.project_name, pr.student_email,
               s.full_name AS student_name,
               p.printer_name
        FROM   print_jobs pj
        JOIN   print_requests pr ON pr.request_id = pj.request_id
        LEFT JOIN students s ON s.email = pr.student_email
        LEFT JOIN printers  p ON p.printer_id = pj.printer_id
        WHERE  pj.status = 'printing'
          AND  pj.print_end_expected IS NOT NULL
          AND  pj.staff_notified = 0
          AND  pj.assigned_by = %s
    """, (current_email,)) or []

    notifications = []
    for job in candidate_jobs:
        end_dt = job.get('print_end_expected')
        if not end_dt:
            continue
        if isinstance(end_dt, str):
            end_dt = datetime.datetime.fromisoformat(end_dt)

        if end_dt <= now:
            note_type = 'print_done'
            message   = f"⏰ Print complete: \"{job['project_name']}\" on {job.get('printer_name','')}"
        elif _job_exceeds_hours(end_dt):
            note_type = 'overschedule'
            message   = f"⚠️ \"{job['project_name']}\" will exceed today's closing time on {job.get('printer_name','')}"
        else:
            continue

        # Atomically claim this notification — only the first caller wins
        rows_updated = db.execute_update(
            "UPDATE print_jobs SET staff_notified = 1 "
            "WHERE job_id = %s AND staff_notified = 0",
            (job['job_id'],)
        )
        # rows_updated == 0 means another process already claimed it; skip
        if not rows_updated or rows_updated < 1:
            continue  # DB helper returned None — skip to be safe

        notifications.append({
            'type':         note_type,
            'job_id':       job['job_id'],
            'project_name': job['project_name'],
            'student_name': job.get('student_name') or job['student_email'],
            'printer_name': job.get('printer_name', ''),
            'message':      message,
        })

    return jsonify({'success': True, 'notifications': notifications}), 200


@admin_bp.route('/api/admin/jobs/reorder', methods=['PATCH'])
def reorder_printer_queue():
    """
    Reorder jobs in a printer's queue.
    Body: { printer_id, order: [job_id, job_id, ...] }
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    payload = AuthService.verify_jwt_token(auth_header.split(' ')[1])
    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    data       = request.json or {}
    printer_id = data.get('printer_id')
    order      = data.get('order', [])
    if not printer_id or not order:
        return jsonify({'success': False, 'message': 'printer_id and order[] are required'}), 400

    for pos, job_id in enumerate(order, start=1):
        db.execute_query(
            "UPDATE print_jobs SET queue_position = %s WHERE job_id = %s AND printer_id = %s",
            (pos, job_id, printer_id)
        )

    return jsonify({'success': True, 'message': 'Queue reordered'}), 200


@admin_bp.route('/api/admin/jobs/<int:job_id>', methods=['DELETE'])
def remove_job(job_id):
    """Remove a job from the queue (sets status to 'cancelled' and returns request to 'approved')."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    payload = AuthService.verify_jwt_token(auth_header.split(' ')[1])
    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    job = db.fetch_one("SELECT job_id, request_id FROM print_jobs WHERE job_id = %s", (job_id,))
    if not job:
        return jsonify({'success': False, 'message': 'Job not found'}), 404

    db.execute_query("UPDATE print_jobs SET status = 'cancelled', completed_at = NOW() WHERE job_id = %s", (job_id,))
    db.execute_query("UPDATE print_requests SET status = 'approved' WHERE request_id = %s", (job['request_id'],))

    return jsonify({'success': True, 'message': 'Job removed from queue'}), 200


# ==================== PRINTER MANAGEMENT ====================

@admin_bp.route('/api/admin/printers', methods=['GET'])
def admin_list_printers():
    """List all printers (Admin only)."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    printers = db.fetch_all(
        "SELECT printer_id, printer_name, model, location, status, notes, created_at FROM printers ORDER BY printer_name"
    ) or []
    return jsonify({'success': True, 'printers': printers}), 200


@admin_bp.route('/api/admin/printers', methods=['POST'])
def admin_add_printer():
    """Add a new printer (Admin only)."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    data = request.json or {}
    name = (data.get('printer_name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Printer name is required'}), 400

    existing = db.fetch_one("SELECT printer_id FROM printers WHERE printer_name = %s", (name,))
    if existing:
        return jsonify({'success': False, 'message': 'A printer with that name already exists'}), 409

    result = db.execute_query(
        "INSERT INTO printers (printer_name, model, location, status, notes) VALUES (%s, %s, %s, %s, %s)",
        (name, (data.get('model') or '').strip() or None,
         (data.get('location') or '').strip() or None,
         data.get('status', 'active'),
         (data.get('notes') or '').strip() or None)
    )
    if result is not None:
        return jsonify({'success': True, 'message': 'Printer added', 'printer_id': result}), 201
    return jsonify({'success': False, 'message': 'Failed to add printer'}), 500


@admin_bp.route('/api/admin/printers/<int:printer_id>', methods=['PATCH'])
def admin_update_printer(printer_id):
    """Update printer details (Admin only)."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    existing = db.fetch_one("SELECT printer_id FROM printers WHERE printer_id = %s", (printer_id,))
    if not existing:
        return jsonify({'success': False, 'message': 'Printer not found'}), 404

    data = request.json or {}
    sets, vals = [], []
    for field in ('printer_name', 'model', 'location', 'status', 'notes'):
        if field in data:
            sets.append(f"{field} = %s")
            vals.append((data[field] or '').strip() or None)
    if not sets:
        return jsonify({'success': False, 'message': 'Nothing to update'}), 400

    vals.append(printer_id)
    db.execute_query(f"UPDATE printers SET {', '.join(sets)} WHERE printer_id = %s", tuple(vals))
    return jsonify({'success': True, 'message': 'Printer updated'}), 200


@admin_bp.route('/api/admin/printers/<int:printer_id>', methods=['DELETE'])
def admin_delete_printer(printer_id):
    """Delete a printer (Admin only)."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    existing = db.fetch_one("SELECT printer_id FROM printers WHERE printer_id = %s", (printer_id,))
    if not existing:
        return jsonify({'success': False, 'message': 'Printer not found'}), 404

    db.execute_query("DELETE FROM printers WHERE printer_id = %s", (printer_id,))
    return jsonify({'success': True, 'message': 'Printer deleted'}), 200


# ==================== ADMIN ACCOUNT MANAGEMENT ====================

@admin_bp.route('/api/admin/admins', methods=['GET'])
def admin_list_admins():
    """List all admin accounts (Admin only)."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    admins = db.fetch_all(
        "SELECT email, full_name, role, email_verified, created_at, last_login FROM admins ORDER BY created_at DESC"
    ) or []
    return jsonify({'success': True, 'admins': admins}), 200


@admin_bp.route('/api/admin/admins', methods=['POST'])
def admin_create_admin():
    """Create a new admin account (Admin only). Sets email_verified = TRUE immediately."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    data = request.json or {}
    email = (data.get('email') or '').strip()
    password = data.get('password', '')
    full_name = (data.get('full_name') or '').strip()
    role = data.get('role', 'admin')

    if not email or not password or not full_name:
        return jsonify({'success': False, 'message': 'email, password, and full_name are required'}), 400
    if role not in ('super_admin', 'admin', 'moderator', 'professor', 'manager'):
        return jsonify({'success': False, 'message': 'Invalid role'}), 400

    existing = db.fetch_one("SELECT email FROM admins WHERE email = %s", (email,))
    if existing:
        return jsonify({'success': False, 'message': 'Email already registered'}), 409

    password_hash = AuthService.hash_password(password)
    result = db.execute_query(
        "INSERT INTO admins (email, password_hash, full_name, role, email_verified) VALUES (%s, %s, %s, %s, TRUE)",
        (email, password_hash, full_name, role)
    )
    if result is not None:
        try:
            inviter_name = payload.get('full_name') or payload.get('email', 'A DGSpace admin')
            EmailService.send_admin_invite_email(
                to_email=email,
                full_name=full_name,
                password=password,
                inviter_name=inviter_name,
            )
        except Exception as email_err:
            print(f"[WARN] Admin invite email failed for {email}: {email_err}")
        return jsonify({'success': True, 'message': 'Admin created successfully'}), 201
    return jsonify({'success': False, 'message': 'Failed to create admin'}), 500


@admin_bp.route('/api/admin/admins/<path:email>', methods=['DELETE'])
def admin_delete_admin(email):
    """Delete an admin account (Admin only). Cannot delete yourself."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    if payload.get('email') == email:
        return jsonify({'success': False, 'message': 'You cannot delete your own account'}), 400

    existing = db.fetch_one("SELECT email, role FROM admins WHERE email = %s", (email,))
    if not existing:
        return jsonify({'success': False, 'message': 'Admin not found'}), 404

    if existing.get('role') == 'super_admin':
        return jsonify({'success': False, 'message': 'The super_admin account cannot be deleted'}), 403

    db.execute_query("DELETE FROM totp_secrets WHERE email = %s AND user_type = 'admin'", (email,))
    db.execute_query("DELETE FROM password_reset_tokens WHERE email = %s AND user_type = 'admin'", (email,))
    db.execute_query("DELETE FROM email_verification_codes WHERE email = %s AND user_type = 'admin'", (email,))
    db.execute_query("DELETE FROM admins WHERE email = %s", (email,))
    return jsonify({'success': True, 'message': 'Admin deleted'}), 200


@admin_bp.route('/api/admin/admins/<path:email>/password', methods=['PATCH'])
def admin_reset_admin_password(email):
    """Reset another admin's password (Admin only). Body: { new_password }"""
    payload = _get_auth_payload()
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    data = request.json or {}
    new_password = data.get('new_password', '').strip()
    if len(new_password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

    existing = db.fetch_one("SELECT email FROM admins WHERE email = %s", (email,))
    if not existing:
        return jsonify({'success': False, 'message': 'Admin not found'}), 404

    new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    db.execute_query("UPDATE admins SET password_hash = %s WHERE email = %s", (new_hash, email))
    return jsonify({'success': True, 'message': 'Password updated successfully'}), 200


@admin_bp.route('/api/admin/print-requests', methods=['GET'])
def admin_get_all_requests():
    """Get all print requests (Admin / Student Staff)"""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)

    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    status = request.args.get('status')
    priority = request.args.get('priority')
    week = request.args.get('week')
    from_date = request.args.get('from')
    to_date = request.args.get('to')

    result = PrintService.get_all_requests(status, priority, week, from_date, to_date)

    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@admin_bp.route('/api/admin/print-requests/<int:request_id>/status', methods=['PATCH'])
def admin_update_request_status(request_id):
    """Update the status of a print request (Admin / Student Staff)"""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)

    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    data = request.json

    if 'status' not in data:
        return jsonify({'success': False, 'message': 'Status is required'}), 400

    valid_statuses = ['approved', 'rejected', 'in_progress', 'completed', 'cancelled', 'revision_requested']
    if data['status'] not in valid_statuses:
        return jsonify({'success': False, 'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400

    result = PrintService.update_request_status(
        request_id=request_id,
        new_status=data['status'],
        admin_email=payload['email'],
        admin_notes=data.get('admin_notes'),
        change_reason=data.get('change_reason'),
        user_type=payload.get('user_type', 'admin')
    )

    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@admin_bp.route('/api/admin/print-requests/<int:request_id>/priority', methods=['PATCH'])
def admin_update_priority(request_id):
    """Update the priority of a print request (Admin / Student Staff only)"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    data = request.json or {}
    priority = data.get('priority', '').strip().lower()
    result = PrintService.update_priority(
        request_id=request_id,
        priority=priority,
        admin_email=payload['email']
    )
    return jsonify(result), (200 if result['success'] else 400)


@admin_bp.route('/api/admin/print-requests/<int:request_id>/return', methods=['POST'])
def admin_return_request(request_id):
    """Return a print request back to the student for revision (Admin / Student Staff)"""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)

    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    data = request.json or {}
    reason = data.get('reason', '').strip()
    unlocked_fields = data.get('unlocked_fields')

    if not reason:
        return jsonify({'success': False, 'message': 'A return reason is required'}), 400

    result = PrintService.return_print_request(
        request_id=request_id,
        admin_email=payload['email'],
        reason=reason,
        unlocked_fields=unlocked_fields,
        user_type=payload.get('user_type', 'admin')
    )

    if result['success']:
        return jsonify(result), 200
    elif 'not found' in result['message']:
        return jsonify(result), 404
    else:
        return jsonify(result), 400


@admin_bp.route('/api/admin/print-requests/<int:request_id>/approve-with-ufp', methods=['POST'])
def admin_approve_with_ufp(request_id):
    """Approve a print request and attach UFP slicer data (Admin only)."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    data = request.json or {}
    ufp_filename           = data.get('ufp_filename', '').strip()
    ufp_original_name      = data.get('ufp_original_name', '').strip()
    ufp_print_time_minutes = data.get('ufp_print_time_minutes')
    ufp_material_g         = data.get('ufp_material_g')
    admin_notes            = data.get('admin_notes', '').strip()

    if not ufp_filename:
        return jsonify({'success': False, 'message': 'ufp_filename is required'}), 400

    try:
        rows = db.fetch_all(
            "SELECT status FROM print_requests WHERE request_id = %s",
            (request_id,)
        )
        if not rows:
            return jsonify({'success': False, 'message': 'Print request not found'}), 404

        current_status = rows[0]['status']
        if current_status not in ('pending', 'revision_requested'):
            return jsonify({
                'success': False,
                'message': f'Request cannot be approved from status: {current_status}'
            }), 400

        reviewer_email = payload['email'] if payload.get('user_type') == 'admin' else None

        db.execute_query(
            """UPDATE print_requests
               SET status                 = 'approved',
                   ufp_file_path          = %s,
                   ufp_original_name      = %s,
                   ufp_print_time_minutes = %s,
                   ufp_material_g         = %s,
                   admin_notes            = %s,
                   reviewed_by            = %s,
                   reviewed_at            = NOW()
               WHERE request_id = %s""",
            (
                ufp_filename,
                ufp_original_name or None,
                ufp_print_time_minutes,
                ufp_material_g,
                admin_notes or None,
                reviewer_email,
                request_id
            )
        )

        db.execute_query(
            """INSERT INTO print_request_history
               (request_id, old_status, new_status, changed_by, change_reason)
               VALUES (%s, %s, 'approved', %s, %s)""",
            (
                request_id,
                current_status,
                payload['email'],
                f'Approved with UFP: {ufp_original_name or ufp_filename}'
                + (f' | Notes: {admin_notes}' if admin_notes else '')
            )
        )

        return jsonify({'success': True, 'message': 'Request approved with UFP data'}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500


@admin_bp.route('/api/admin/print-requests/statistics', methods=['GET'])
def admin_get_statistics():
    """Get print request statistics (Admin / Student Staff)"""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)

    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    result = PrintService.get_statistics()

    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


# ==================== 2FA (TOTP) ENDPOINTS ====================

@admin_bp.route('/api/2fa/status', methods=['GET'])
def get_2fa_status():
    """Return the 2FA enabled status for the current user."""
    payload = _get_auth_payload()
    if not payload:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    status = TotpService.get_totp_status(payload['email'], payload['user_type'])
    return jsonify({'success': True, **status}), 200


@admin_bp.route('/api/2fa/setup', methods=['POST'])
def setup_2fa():
    """Generate a new TOTP secret and return a QR code (Base64 PNG)."""
    payload = _get_auth_payload()
    if not payload:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    result = TotpService.setup_totp(payload['email'], payload['user_type'])
    return jsonify(result), 200 if result['success'] else 500


@admin_bp.route('/api/admin/migrate-totp-enum', methods=['POST'])
def migrate_totp_enum():
    """ONE-TIME FIX: Add student_staff to totp_secrets.user_type ENUM."""
    payload = _get_auth_payload()
    if not payload:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        db.execute_query("""
            ALTER TABLE totp_secrets
              MODIFY COLUMN user_type ENUM('student', 'admin', 'student_staff') NOT NULL
        """)
        return jsonify({'success': True, 'message': 'ENUM updated'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/2fa/debug', methods=['GET'])
def debug_2fa():
    """Temporary debug: show server time and expected TOTP code for the current user."""
    import pyotp as _pyotp
    payload = _get_auth_payload()
    if not payload:
        return jsonify({'error': 'Unauthorized'}), 401
    row = db.fetch_one(
        "SELECT secret, is_active FROM totp_secrets WHERE email = %s AND user_type = %s",
        (payload['email'], payload['user_type'])
    )
    if not row:
        return jsonify({'error': 'No totp_secrets row found', 'email': payload['email'], 'user_type': payload['user_type']})
    totp = _pyotp.TOTP(row['secret'])
    now = datetime.datetime.utcnow()
    return jsonify({
        'server_utc': now.isoformat(),
        'server_timestamp': int(now.timestamp()),
        'expected_code': totp.now(),
        'is_active': row['is_active'],
        'user_type_in_jwt': payload['user_type'],
        'email': payload['email'],
    })


@admin_bp.route('/api/2fa/confirm', methods=['POST'])
def confirm_2fa():
    """
    Activate 2FA: after scanning the QR code, submit the 6-digit code shown in the TOTP app.
    Body: { "code": "123456" }
    """
    payload = _get_auth_payload()
    if not payload:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.json or {}
    code = data.get('code', '').strip()
    if not code:
        return jsonify({'success': False, 'message': 'The "code" field is required'}), 400

    result = TotpService.confirm_totp(payload['email'], payload['user_type'], code)
    return jsonify(result), 200 if result['success'] else 400


@admin_bp.route('/api/2fa/verify', methods=['POST'])
def verify_2fa():
    """
    Login step 2: verify TOTP code and issue a full JWT.
    Body: { "email": "...", "user_type": "student|admin", "code": "123456" }
    """
    data = request.json or {}
    email = data.get('email', '').strip()
    user_type = data.get('user_type', 'student')
    code = data.get('code', '').strip()

    if not email or not code:
        return jsonify({'success': False, 'message': '"email" and "code" are both required'}), 400

    result = TotpService.verify_totp(email, user_type, code)
    if not result['success']:
        return jsonify(result), 401

    if user_type == 'admin':
        admin_row = db.fetch_one("SELECT role FROM admins WHERE email = %s", (email,))
        role = admin_row.get('role') if admin_row else None
        jwt_payload = {
            'email': email,
            'user_type': user_type,
            'role': role,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=Config.JWT_EXPIRATION_HOURS),
            'iat': datetime.datetime.utcnow()
        }
        token = _jwt.encode(jwt_payload, Config.JWT_SECRET_KEY, algorithm='HS256')
    else:
        token = AuthService.generate_jwt_token(email, user_type)

    return jsonify({
        'success': True,
        'message': '2FA verified successfully',
        'token': token
    }), 200


@admin_bp.route('/api/2fa/login-verify', methods=['POST'])
def login_verify_2fa():
    """
    Login step 2 (secure): verify temp_token + TOTP code, then issue a full JWT.
    Body: { "temp_token": "...", "code": "123456" }
    """
    data = request.json or {}
    temp_token = data.get('temp_token', '').strip()
    code       = data.get('code', '').strip()

    if not temp_token or not code:
        return jsonify({'success': False, 'message': '"temp_token" and "code" are both required'}), 400

    tp = AuthService.verify_jwt_token(temp_token)
    if not tp or tp.get('scope') != '2fa_pending':
        return jsonify({'success': False, 'message': 'Invalid or expired session — please log in again'}), 401

    email          = tp['email']
    user_type      = tp['user_type']
    effective_type = tp.get('effective_type', user_type)

    result = TotpService.verify_totp(email, user_type, code)
    if not result['success']:
        return jsonify({'success': False, 'message': 'Invalid code — please try again'}), 401

    if user_type == 'admin':
        role = tp.get('role')
        jwt_payload = {
            'email': email,
            'user_type': user_type,
            'role': role,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=Config.JWT_EXPIRATION_HOURS),
            'iat': datetime.datetime.utcnow()
        }
        token = _jwt.encode(jwt_payload, Config.JWT_SECRET_KEY, algorithm='HS256')
    else:
        token = AuthService.generate_jwt_token(email, effective_type)

    table = 'students' if user_type == 'student' else 'admins'
    user_row = db.fetch_one(f"SELECT email, full_name, role FROM {table} WHERE email = %s", (email,))
    user_obj = {
        'email': email,
        'full_name': user_row['full_name'] if user_row else email,
        'user_type': effective_type,
        **({'role': tp.get('role')} if user_type != 'student' else {})
    }

    return jsonify({'success': True, 'token': token, 'user': user_obj}), 200


@admin_bp.route('/api/2fa/disable', methods=['DELETE'])
def disable_2fa():
    """Disable 2FA for the current user."""
    payload = _get_auth_payload()
    if not payload:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    result = TotpService.disable_totp(payload['email'], payload['user_type'])
    return jsonify(result), 200


@admin_bp.route('/api/admin/students/<email>/2fa', methods=['DELETE'])
def admin_reset_student_2fa(email):
    """Admin: forcibly clear a specific student's 2FA."""
    payload = _get_auth_payload()
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    result = TotpService.disable_totp(email, 'student')
    return jsonify(result), 200 if result['success'] else 400


# ===========================================================================
# Weekly Report / Dashboard
# ===========================================================================

@admin_bp.route('/api/reports/dashboard', methods=['GET'])
def get_dashboard_report():
    """
    GET /api/reports/dashboard?from=YYYY-MM-DD&to=YYYY-MM-DD
    GET /api/reports/dashboard?all_time=1
    Return aggregated stats from print_requests table.
    """
    payload = _get_auth_payload()
    if not payload or payload.get('user_type') not in ('admin', 'professor', 'manager'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    all_time  = request.args.get('all_time', '').strip() == '1'
    from_date = request.args.get('from', '').strip() or None
    to_date   = request.args.get('to',   '').strip() or None

    if not all_time and (not from_date or not to_date):
        to_dt   = datetime.datetime.utcnow()
        from_dt = to_dt - datetime.timedelta(days=7)
        from_date = from_dt.strftime('%Y-%m-%d')
        to_date   = to_dt.strftime('%Y-%m-%d')

    where    = "" if all_time else "WHERE DATE(created_at) BETWEEN %s AND %s"
    params   = () if all_time else (from_date, to_date)
    where_pr = "" if all_time else "WHERE DATE(pr.created_at) BETWEEN %s AND %s"

    try:
        summary = db.fetch_one(f"""
            SELECT
                COUNT(*) AS total_requests,
                SUM(status = 'completed') AS completed,
                SUM(status IN ('queued', 'printing')) AS in_progress,
                SUM(status = 'pending') AS pending,
                SUM(status = 'approved') AS approved,
                SUM(status = 'rejected') AS rejected,
                SUM(status = 'cancelled') AS cancelled,
                ROUND(SUM(COALESCE(ufp_print_time_minutes, slicer_time_minutes)) / 60, 1) AS total_print_hours,
                ROUND(SUM(COALESCE(ufp_material_g, slicer_material_g)), 1) AS total_material_g,
                COUNT(DISTINCT student_email) AS unique_students
            FROM print_requests
            {where}
        """, params)

        by_material = db.fetch_all(f"""
            SELECT material_type, COUNT(*) AS count,
                   ROUND(SUM(COALESCE(ufp_material_g, slicer_material_g)), 1) AS material_g
            FROM print_requests
            {where}
            GROUP BY material_type
            ORDER BY count DESC
        """, params)

        by_day = db.fetch_all(f"""
            SELECT DATE(created_at) AS day, COUNT(*) AS count,
                   SUM(status = 'completed') AS completed
            FROM print_requests
            {where}
            GROUP BY DATE(created_at)
            ORDER BY day
        """, params)

        top_students = db.fetch_all(f"""
            SELECT pr.student_email, s.full_name,
                   COUNT(*) AS request_count,
                   SUM(pr.status = 'completed') AS completed
            FROM print_requests pr
            LEFT JOIN students s ON pr.student_email = s.email
            {where_pr}
            GROUP BY pr.student_email, s.full_name
            ORDER BY request_count DESC
            LIMIT 10
        """, params)

        recent = db.fetch_all(f"""
            SELECT pr.request_id, pr.student_email, s.full_name,
                   pr.project_name, pr.material_type,
                   pr.slicer_time_minutes, pr.slicer_material_g,
                   pr.status, pr.created_at, pr.completed_at
            FROM print_requests pr
            LEFT JOIN students s ON pr.student_email = s.email
            {where_pr}
            ORDER BY pr.created_at DESC
            LIMIT 50
        """, params)

        def serialize(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            return obj

        recent_list  = [{k: serialize(v) for k, v in r.items()} for r in recent]
        by_day_list  = [{k: serialize(v) for k, v in r.items()} for r in by_day]

        return jsonify({
            'success': True,
            'all_time': all_time,
            'period': {'from': from_date, 'to': to_date},
            'summary': summary,
            'by_material': by_material,
            'by_day': by_day_list,
            'top_students': top_students,
            'recent': recent_list,
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Report error: {str(e)}'}), 500
