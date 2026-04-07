from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from database import db
from auth_service import AuthService
from email_service import EmailService, mail
from config import Config
from print_service import PrintService
from totp_service import TotpService
from ufp_analysis import analyze_ufp
from apscheduler.schedulers.background import BackgroundScheduler
import os
import uuid
import bcrypt
from datetime import date, datetime
import decimal

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

# ── Custom JSON serializer — handles datetime / date / Decimal ────────────────
class _AppEncoder(app.json_provider_class):
    def default(self, o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super().default(o)

app.json_provider_class = _AppEncoder
app.json = _AppEncoder(app)
CORS(app)  # Enable CORS for frontend requests

# Configure flask-mailman (Flask 3.x compatible replacement for Flask-Mail)
app.config['MAIL_SERVER'] = Config.MAIL_SERVER
app.config['MAIL_PORT'] = Config.MAIL_PORT
app.config['MAIL_USE_TLS'] = Config.MAIL_USE_TLS
app.config['MAIL_USERNAME'] = Config.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = Config.MAIL_PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = Config.MAIL_DEFAULT_SENDER
app.config['MAIL_USE_LOCALTIME'] = False

# Configure upload folder
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

mail.init_app(app)

# ── 2-week file cleanup job ───────────────────────────────────────────────────
def _cleanup_old_files():
    """
    Runs every 24 h.
    - UFP + STL: purge for completed/failed/revision_requested (no time gate — safe to delete once terminal)
    - STL only:  also purge for approved/queued/printing (STL not needed once UFP uploaded)
    Sets file_deleted = 1 so record stays in DB.
    """
    try:
        upload_dir = Config.UPLOAD_FOLDER
        print(f"[cleanup] UPLOAD_FOLDER = {upload_dir}")

        # Diagnostic: how many records have files at all?
        total_with_files = db.fetch_one(
            "SELECT COUNT(*) AS cnt FROM print_requests WHERE ufp_file_path IS NOT NULL OR stl_file_path IS NOT NULL",
            ()
        )
        print(f"[cleanup] Records with files in DB: {(total_with_files or {}).get('cnt', '?')}")

        # ── Batch 1: terminal statuses — delete both UFP and STL (no time gate) ──
        eligible = db.fetch_all(
            """
            SELECT request_id, ufp_file_path, stl_file_path
            FROM   print_requests
            WHERE  file_deleted = 0
              AND  (ufp_file_path IS NOT NULL OR stl_file_path IS NOT NULL)
              AND  status IN ('completed', 'failed', 'revision_requested')
            """,
            ()
        )
        purged = 0
        for row in (eligible or []):
            for col in ('ufp_file_path', 'stl_file_path'):
                path = row.get(col)
                if path:
                    full_path = os.path.join(upload_dir, os.path.basename(path))
                    try:
                        if os.path.exists(full_path):
                            os.remove(full_path)
                            print(f"[cleanup] Deleted: {full_path}")
                        else:
                            print(f"[cleanup] Already gone: {full_path}")
                    except Exception as ex:
                        print(f"[cleanup] Failed to delete {full_path}: {ex}")
            db.execute_query(
                "UPDATE print_requests SET file_deleted = 1, ufp_file_path = NULL, stl_file_path = NULL WHERE request_id = %s",
                (row['request_id'],)
            )
            purged += 1
        print(f"[cleanup] Terminal purge — processed {purged} record(s).")

        # ── Batch 2: active statuses — delete STL only (UFP still needed) ──
        stl_early = db.fetch_all(
            """
            SELECT request_id, stl_file_path
            FROM   print_requests
            WHERE  stl_file_path IS NOT NULL
              AND  status IN ('approved', 'queued', 'printing')
            """,
            ()
        )
        stl_purged = 0
        for row in (stl_early or []):
            path = row.get('stl_file_path')
            if path:
                full_path = os.path.join(upload_dir, os.path.basename(path))
                try:
                    if os.path.exists(full_path):
                        os.remove(full_path)
                        print(f"[cleanup] Deleted STL: {full_path}")
                    else:
                        print(f"[cleanup] STL already gone: {full_path}")
                except Exception as ex:
                    print(f"[cleanup] Failed to delete STL {full_path}: {ex}")
            db.execute_query(
                "UPDATE print_requests SET stl_file_path = NULL WHERE request_id = %s",
                (row['request_id'],)
            )
            stl_purged += 1
        print(f"[cleanup] Active STL purge — processed {stl_purged} record(s).")

        # ── Batch 3: orphan files — on disk but no matching DB record ──
        # Covers files whose DB path was already NULLed but file was never deleted
        # (e.g. when UPLOAD_FOLDER env var was wrong on a previous deploy)
        try:
            all_files = set(os.listdir(upload_dir))
        except Exception as ex:
            print(f"[cleanup] Cannot list upload dir: {ex}")
            all_files = set()

        # Collect all filenames still referenced in DB
        referenced = set()
        for col in ('ufp_file_path', 'stl_file_path'):
            rows = db.fetch_all(f"SELECT {col} AS p FROM print_requests WHERE {col} IS NOT NULL", ()) or []
            for r in rows:
                p = r.get('p')
                if p:
                    referenced.add(os.path.basename(p))

        orphans = [f for f in all_files if f not in referenced and (f.endswith('.stl') or f.endswith('.ufp'))]
        orphan_purged = 0
        for fname in orphans:
            full_path = os.path.join(upload_dir, fname)
            try:
                os.remove(full_path)
                print(f"[cleanup] Deleted orphan: {full_path}")
                orphan_purged += 1
            except Exception as ex:
                print(f"[cleanup] Failed to delete orphan {full_path}: {ex}")
        print(f"[cleanup] Orphan purge — deleted {orphan_purged} of {len(orphans)} orphan file(s) found.")

    except Exception as e:
        print(f"[cleanup] Error: {e}")


from datetime import datetime as _dt_now
_scheduler = BackgroundScheduler(daemon=True)
# next_run_time=_dt_now.now() → runs immediately on startup, then every 24 h
_scheduler.add_job(_cleanup_old_files, 'interval', hours=24, id='file_cleanup',
                   next_run_time=_dt_now.now())

# ── Unverified-account cleanup (runs via scheduler, NOT on every request) ─────
def _cleanup_unverified():
    """Delete unverified accounts/codes older than 10 minutes. Runs every 10 min."""
    try:
        db.execute_query(
            "DELETE FROM email_verification_codes "
            "WHERE is_used = FALSE AND expires_at < NOW() "
            "AND email IN (SELECT email FROM students WHERE email_verified = FALSE)"
        )
        db.execute_query(
            "DELETE FROM students "
            "WHERE email_verified = FALSE "
            "AND created_at < DATE_SUB(NOW(), INTERVAL 10 MINUTE)"
        )
    except Exception as e:
        print(f"[cleanup_unverified] {e}")

_scheduler.add_job(_cleanup_unverified, 'interval', minutes=10, id='unverified_cleanup')
_scheduler.start()


@app.route('/api/admin/cleanup', methods=['POST'])
def manual_cleanup():
    """Admin-only: trigger file cleanup immediately and return a summary."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    payload = AuthService.verify_jwt_token(auth_header.split(' ')[1])
    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    # Scan candidate dirs to find where files actually live
    scan_dirs = ['/app/uploads', '/data', '/app', '/tmp']
    dir_info = {}
    for d in scan_dirs:
        if os.path.isdir(d):
            try:
                files = os.listdir(d)
                stl_ufp = [f for f in files if f.endswith('.stl') or f.endswith('.ufp')]
                total_bytes = sum(
                    os.path.getsize(os.path.join(d, f))
                    for f in stl_ufp
                    if os.path.isfile(os.path.join(d, f))
                )
                dir_info[d] = {'count': len(stl_ufp), 'size_mb': round(total_bytes / 1024 / 1024, 2)}
            except Exception as ex:
                dir_info[d] = {'error': str(ex)}
        else:
            dir_info[d] = {'exists': False}

    import sys, io
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        _cleanup_old_files()
    finally:
        sys.stdout = old_stdout
    log_output = buf.getvalue()
    return jsonify({'success': True, 'log': log_output, 'dirs': dir_info}), 200


@app.before_request
def before_request():
    # Connection check is a no-op now (pool handles reconnects),
    # but kept for backward-compat in case anything calls db.connect() directly.
    if not db.connection or not db.connection.is_connected():
        db.connect()

# Health check endpoint
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'message': 'DGSpace API is running',
        'version': '1.0.0'
    })

# ==================== STUDENT ENDPOINTS ====================

@app.route('/api/students/register', methods=['POST'])
def register_student():
    """Register a new student"""
    data = request.json
    
    # Validate required fields
    required_fields = ['email', 'password', 'full_name']
    if not all(field in data for field in required_fields):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    # Register student
    result = AuthService.register_student(
        email=data['email'],
        password=data['password'],
        full_name=data['full_name'],
        department=data.get('department')
    )
    
    if result['success']:
        # Create verification code
        code_result = AuthService.create_verification_code(data['email'], 'student')
        
        if code_result['success']:
            if Config.DEV_EMAIL_MODE:
                # Dev mode: print code to terminal instead of sending email
                print(f"[DEV] Verification code for {data['email']}: {code_result['code']}")
            else:
                EmailService.send_verification_email(
                    to_email=data['email'],
                    verification_code=code_result['code'],
                    full_name=data['full_name']
                )
            return jsonify({
                'success': True,
                'message': 'Registration successful! Please check your email for verification code.'
            }), 201
        else:
            return jsonify(result), 500
    else:
        return jsonify(result), 400

@app.route('/api/students/verify-email', methods=['POST'])
def verify_student_email():
    """Verify student email with code"""
    data = request.json
    
    if not all(field in data for field in ['email', 'code']):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    result = AuthService.verify_email_code(data['email'], 'student', data['code'])
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400

@app.route('/api/students/login', methods=['POST'])
def login_student():
    """Student login"""
    data = request.json
    
    if not all(field in data for field in ['email', 'password']):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    result = AuthService.login(data['email'], data['password'], 'student')
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 401

@app.route('/api/students/resend-verification', methods=['POST'])
def resend_student_verification():
    """Resend verification code to student"""
    data = request.json
    
    if 'email' not in data:
        return jsonify({'success': False, 'message': 'Email is required'}), 400
    
    # Get student info
    student = db.fetch_one("SELECT full_name FROM students WHERE email = %s", (data['email'],))
    
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404
    
    # Create new verification code
    code_result = AuthService.create_verification_code(data['email'], 'student')
    
    if code_result['success']:
        # Send verification email
        EmailService.send_verification_email(
            to_email=data['email'],
            verification_code=code_result['code'],
            full_name=student['full_name']
        )
        return jsonify({'success': True, 'message': 'Verification code sent'}), 200
    else:
        return jsonify({'success': False, 'message': 'Failed to send verification code'}), 500

# ==================== ADMIN ENDPOINTS ====================

@app.route('/api/admins/register', methods=['POST'])
def register_admin():
    """Register a new admin"""
    data = request.json
    
    # Validate required fields
    required_fields = ['email', 'password', 'full_name']
    if not all(field in data for field in required_fields):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    # Register admin
    result = AuthService.register_admin(
        email=data['email'],
        password=data['password'],
        full_name=data['full_name'],
        role=data.get('role', 'admin')
    )
    
    if result['success']:
        # Create verification code
        code_result = AuthService.create_verification_code(data['email'], 'admin')
        
        if code_result['success']:
            # Send verification email
            EmailService.send_verification_email(
                to_email=data['email'],
                verification_code=code_result['code'],
                full_name=data['full_name']
            )
            return jsonify({
                'success': True,
                'message': 'Admin registration successful! Please check your email for verification code.'
            }), 201
        else:
            return jsonify(result), 500
    else:
        return jsonify(result), 400

@app.route('/api/admins/verify-email', methods=['POST'])
def verify_admin_email():
    """Verify admin email with code"""
    data = request.json
    
    if not all(field in data for field in ['email', 'code']):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    result = AuthService.verify_email_code(data['email'], 'admin', data['code'])
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400

@app.route('/api/admins/login', methods=['POST'])
def login_admin():
    """Admin login"""
    data = request.json
    
    if not all(field in data for field in ['email', 'password']):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    result = AuthService.login(data['email'], data['password'], 'admin')
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 401

# ==================== PROTECTED ENDPOINTS ====================

@app.route('/api/profile', methods=['GET'])
def get_profile():
    """Get user profile (requires authentication)"""
    # Get token from Authorization header
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    
    if not payload:
        return jsonify({'success': False, 'message': 'Invalid or expired token'}), 401
    
    # Get user data from database
    table = 'students' if payload['user_type'] == 'student' else 'admins'
    query = f"SELECT email, full_name FROM {table} WHERE email = %s"
    user = db.fetch_one(query, (payload['email'],))
    
    if user:
        return jsonify({
            'success': True,
            'user': {
                'email': user['email'],
                'full_name': user['full_name'],
                'user_type': payload['user_type']
            }
        }), 200
    else:
        return jsonify({'success': False, 'message': 'User not found'}), 404


@app.route('/api/profile/change-password', methods=['POST'])
def change_password():
    """Change the logged-in user's password.
    Body: { "current_password": "...", "new_password": "..." }
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.json or {}
    current_pw = data.get('current_password', '').strip()
    new_pw = data.get('new_password', '').strip()

    if not current_pw or not new_pw:
        return jsonify({'success': False, 'message': 'Both fields are required'}), 400
    if len(new_pw) < 8:
        return jsonify({'success': False, 'message': 'New password must be at least 8 characters'}), 400

    table = 'students' if payload['user_type'] in ('student', 'student_staff') else 'admins'
    row = db.fetch_one(f"SELECT password_hash FROM {table} WHERE email = %s", (payload['email'],))
    if not row:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    if not bcrypt.checkpw(current_pw.encode(), row['password_hash'].encode()):
        return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400

    new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
    db.execute_query(f"UPDATE {table} SET password_hash = %s WHERE email = %s", (new_hash, payload['email']))
    return jsonify({'success': True, 'message': 'Password updated successfully'}), 200


# ==================== 3D PRINT REQUEST ENDPOINTS ====================

@app.route('/api/print-requests/upload-stl', methods=['POST'])
def upload_stl():
    """Upload a .stl file before submitting a print request (Student / Student Staff)"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('student', 'student_staff'):
        return jsonify({'success': False, 'message': 'Invalid token or not a student'}), 401

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400

    original_name = file.filename
    if not original_name.lower().endswith('.stl'):
        return jsonify({'success': False, 'message': 'Only .stl files are allowed'}), 400

    # Save as uuid.stl to avoid filename collisions
    saved_name = f"{uuid.uuid4().hex}.stl"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_name)
    file.save(save_path)

    return jsonify({
        'success': True,
        'filename': saved_name,
        'original_name': original_name
    }), 201

@app.route('/api/print-requests/upload-stl/<filename>', methods=['DELETE'])
def delete_uploaded_stl(filename: str):
    """Delete a previously uploaded STL file before submitting a print request (Student / Student Staff)

    This supports the frontend "Remove" button so mistaken uploads don't linger on disk.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('student', 'student_staff'):
        return jsonify({'success': False, 'message': 'Invalid token or not a student'}), 401

    # Basic path-traversal protection: only allow the basename.
    safe_name = os.path.basename(filename)
    if safe_name != filename:
        return jsonify({'success': False, 'message': 'Invalid filename'}), 400

    upload_dir = f"{app.config['UPLOAD_FOLDER']}"
    file_path = os.path.join(upload_dir, safe_name)

    # Ensure the resolved path stays within the uploads directory.
    abs_upload_dir = os.path.abspath(upload_dir)
    abs_file_path = os.path.abspath(file_path)
    if not abs_file_path.startswith(abs_upload_dir + os.sep):
        return jsonify({'success': False, 'message': 'Invalid filename'}), 400

    if not os.path.exists(abs_file_path):
        # Idempotent: removing twice should be fine.
        return jsonify({'success': True, 'message': 'File already deleted'}), 200

    try:
        os.remove(abs_file_path)
        return jsonify({'success': True, 'message': 'File deleted'}), 200
    except OSError:
        return jsonify({'success': False, 'message': 'Failed to delete file'}), 500


@app.route('/api/print-requests/upload-ufp', methods=['POST'])
def upload_ufp():
    """Upload a .ufp (Ultimaker Format Package) file and return slicer estimates.

    The .ufp is a ZIP archive produced by Cura. We extract print.json from it
    to read the exact print time and material usage the slicer calculated.
    The file is saved temporarily (same uploads folder) so the frontend can
    reference it like an STL if needed.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('student', 'admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400

    original_name = file.filename
    if not original_name.lower().endswith('.ufp'):
        return jsonify({'success': False, 'message': 'Only .ufp files are allowed'}), 400

    # Size limit: 100 MB (UFP contains G-code which can be large)
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 100 * 1024 * 1024:
        return jsonify({'success': False, 'message': 'File exceeds 100 MB limit'}), 400

    saved_name = f"{uuid.uuid4().hex}.ufp"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_name)
    file.save(save_path)

    result = analyze_ufp(save_path)

    if not result.get('success'):
        # Clean up on parse failure
        try:
            os.remove(save_path)
        except OSError:
            pass
        return jsonify(result), 400

    return jsonify({
        'success':       True,
        'filename':      saved_name,
        'original_name': original_name,
        'analysis': {
            'print_time':            result['print_time'],           # {hours, minutes, total_minutes, total_hours}
            'material_weight_g':     result['material_weight_g'],    # grams or None
            'material_length_mm':    result['material_length_mm'],   # mm or None
            'layer_height':          result['layer_height'],
            'infill_sparse_density': result['infill_sparse_density'],
            'material_type':         result['material_type'],
            'printer_name':          result['printer_name'],
        }
    }), 201


@app.route('/api/print-requests/upload-ufp/<filename>', methods=['DELETE'])
def delete_uploaded_ufp(filename: str):
    """Delete a previously uploaded UFP file."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') not in ('student', 'admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    safe_name = os.path.basename(filename)
    abs_upload_dir = os.path.abspath(app.config['UPLOAD_FOLDER'])
    abs_file_path  = os.path.abspath(os.path.join(abs_upload_dir, safe_name))
    if not abs_file_path.startswith(abs_upload_dir + os.sep):
        return jsonify({'success': False, 'message': 'Invalid filename'}), 400

    if not os.path.exists(abs_file_path):
        return jsonify({'success': True, 'message': 'File already deleted'}), 200

    try:
        os.remove(abs_file_path)
        return jsonify({'success': True, 'message': 'File deleted'}), 200
    except OSError:
        return jsonify({'success': False, 'message': 'Failed to delete file'}), 500


@app.route('/api/uploads/<filename>', methods=['GET'])
def serve_upload(filename: str):
    """Serve uploaded STL files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/api/print-requests', methods=['POST'])
def create_print_request():
    """Create a new 3D print request (Student / Student Staff)"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    
    if not payload or payload.get('user_type') not in ('student', 'student_staff', 'admin'):
        return jsonify({'success': False, 'message': 'Invalid token or not a student'}), 401

    data = request.json

    if 'project_name' not in data:
        return jsonify({'success': False, 'message': 'Project name is required'}), 400

    result = PrintService.create_print_request(
        student_email=payload['email'],
        project_name=data['project_name'],
        description=data.get('description'),
        material_type=data.get('material_type', 'PLA'),
        color_preference=data.get('color_preference'),
        is_senior_design=bool(data.get('is_senior_design', False)),
        project_context=data.get('project_context', 'individual'),
        estimated_weight_grams=data.get('estimated_weight_grams'),
        estimated_print_time_hours=data.get('estimated_print_time_hours'),
        priority=data.get('priority', 'normal'),
        stl_file_path=data.get('stl_file_path'),
        stl_original_name=data.get('stl_original_name'),
        slicer_time_minutes=float(data['slicer_time_minutes']) if data.get('slicer_time_minutes') else None,
        slicer_material_g=float(data['slicer_material_g']) if data.get('slicer_material_g') else None,
        deadline_date=data.get('deadline_date') or None,
    )
    
    if result['success']:
        return jsonify(result), 201
    else:
        return jsonify(result), 400


@app.route('/api/print-requests/my-requests', methods=['GET'])
def get_my_requests():
    """Get all print requests for the authenticated student"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    
    if not payload or payload.get('user_type') not in ('student', 'student_staff'):
        return jsonify({'success': False, 'message': 'Invalid token or not a student'}), 401
    
    status = request.args.get('status')
    result = PrintService.get_student_requests(payload['email'], status)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route('/api/print-requests/<int:request_id>', methods=['GET'])
def get_request_details(request_id):
    """Get details of a specific print request"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    
    if not payload:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401
    
    result = PrintService.get_request_by_id(request_id)
    
    if not result['success']:
        return jsonify(result), 404
    
    if payload.get('user_type') == 'student':
        if result['request']['student_email'] != payload['email']:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    elif payload.get('user_type') == 'student_staff':
        # student_staff can view their own requests and all requests (admin view handles the rest)
        pass
    
    return jsonify(result), 200


@app.route('/api/print-requests/<int:request_id>', methods=['DELETE'])
def delete_print_request(request_id):
    """Delete a pending print request (student only, own requests)"""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)

    if not payload:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    if payload.get('user_type') not in ('student', 'student_staff'):
        return jsonify({'success': False, 'message': 'Only students can delete requests'}), 403

    result = PrintService.delete_print_request(request_id, payload['email'])

    if result['success']:
        return jsonify(result), 200
    else:
        # 404 if not found, 403 if wrong owner, 400 if wrong status
        if 'not found' in result['message']:
            return jsonify(result), 404
        if 'Unauthorized' in result['message']:
            return jsonify(result), 403
        return jsonify(result), 400


@app.route('/api/print-requests/<int:request_id>/resubmit', methods=['PATCH'])
def resubmit_print_request(request_id):
    """Student resubmits a revision_requested request in-place (replace STL, edit fields, reset to pending)"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401

    if payload.get('user_type') not in ('student', 'student_staff'):
        return jsonify({'success': False, 'message': 'Only students can resubmit requests'}), 403

    data = request.json or {}

    result = PrintService.resubmit_request(
        request_id=request_id,
        student_email=payload['email'],
        project_name=data.get('project_name'),
        description=data.get('description'),
        stl_file_path=data.get('stl_file_path'),
        stl_original_name=data.get('stl_original_name'),
        material_type=data.get('material_type'),
        color_preference=data.get('color_preference'),
    )

    if result['success']:
        return jsonify(result), 200
    if 'not found' in result['message']:
        return jsonify(result), 404
    if 'Unauthorized' in result['message']:
        return jsonify(result), 403
    return jsonify(result), 400


@app.route('/api/print-requests/<int:request_id>/history', methods=['GET'])
def get_request_history(request_id):
    """Get status change history for a print request"""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    
    if not payload:
        return jsonify({'success': False, 'message': 'Invalid token'}), 401
    
    request_result = PrintService.get_request_by_id(request_id)
    
    if not request_result['success']:
        return jsonify(request_result), 404
    
    if payload.get('user_type') == 'student':
        if request_result['request']['student_email'] != payload['email']:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    result = PrintService.get_request_history(request_id)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


# ==================== ADMIN PRINT REQUEST ENDPOINTS ====================

# ==================== ADMIN USER MANAGEMENT ====================


@app.route('/api/admin/students', methods=['GET'])
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


@app.route('/api/admin/students/<email>', methods=['DELETE'])
def admin_delete_student(email: str):
    """Delete a student account (Admin only).

    Note: print_requests has a FK ON DELETE CASCADE on student_email, so the
    student's print requests and their history will be deleted automatically.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    # Defensive: avoid deleting admins accidentally via weird routing.
    if not email or '@' not in email:
        return jsonify({'success': False, 'message': 'Invalid email'}), 400

    existing = db.fetch_one("SELECT email FROM students WHERE email = %s", (email,))
    if not existing:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    # Also clean up any 2FA secrets, password reset tokens, and verification codes.
    db.execute_query("DELETE FROM totp_secrets WHERE email = %s AND user_type = 'student'", (email,))
    db.execute_query("DELETE FROM password_reset_tokens WHERE email = %s AND user_type = 'student'", (email,))
    db.execute_query("DELETE FROM email_verification_codes WHERE email = %s AND user_type = 'student'", (email,))

    delete_result = db.execute_query("DELETE FROM students WHERE email = %s", (email,))
    if delete_result is None:
        return jsonify({'success': False, 'message': 'Failed to delete student'}), 500

    return jsonify({'success': True, 'message': 'Student deleted'}), 200


@app.route('/api/admin/students/<email>/role', methods=['PATCH'])
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

@app.route('/api/admin/production-board', methods=['GET'])
def get_production_board():
    """
    Return everything needed for the Production Board in one call:
      - ready_to_schedule: approved requests that have a UFP and no active job
      - printers:          each printer with its active queue (queued/printing jobs)
    Access: admin or student_staff.
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    payload = AuthService.verify_jwt_token(auth_header.split(' ')[1])
    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    # ── Ready to Schedule ─────────────────────────────────────────────────
    # Approved requests that have a UFP but no active (non-cancelled) job yet
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

    # ── Printer Queues ────────────────────────────────────────────────────
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


@app.route('/api/admin/print-requests/<int:request_id>/assign', methods=['POST'])
def assign_to_printer(request_id):
    """
    Assign an approved request to a printer queue.
    Body: { printer_id, estimated_start?, estimated_end?, notes? }
    Creates a print_job record and moves the request status to 'queued'.
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

    # Validate request
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

    # Validate printer
    printer = db.fetch_one("SELECT printer_id, status FROM printers WHERE printer_id = %s", (printer_id,))
    if not printer:
        return jsonify({'success': False, 'message': 'Printer not found'}), 404
    if printer['status'] != 'active':
        return jsonify({'success': False, 'message': f'Printer is not active (status: {printer["status"]})'}), 409

    # Check for existing active job on this request
    existing_job = db.fetch_one(
        "SELECT job_id FROM print_jobs WHERE request_id = %s AND status NOT IN ('cancelled','failed')",
        (request_id,)
    )
    if existing_job:
        return jsonify({'success': False, 'message': 'This request already has an active print job'}), 409

    # Determine queue position (append to end)
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

    # Advance request status to 'queued'
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


@app.route('/api/admin/jobs/<int:job_id>/status', methods=['PATCH'])
def update_job_status(job_id):
    """
    Advance a print job through its lifecycle.
    Body: { status: 'file_transferred'|'printing'|'completed'|'failed'|'cancelled', notes? }

    Special behaviour on 'failed':
      - Attempt 1 or 2 → mark job failed, create a new job (attempt+1) on same printer,
        return request to 'queued' so it stays in the queue.
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

    # ── Guard: only one job can be printing per printer ───────────────────
    if new_status == 'printing':
        already = db.fetch_one(
            "SELECT job_id FROM print_jobs "
            "WHERE printer_id = %s AND status = 'printing' AND job_id != %s",
            (job['printer_id'], job_id)
        )
        if already:
            return jsonify({
                'success': False,
                'message': 'Another job is already printing on this printer. '
                           'Finish or fail that job first.'
            }), 400

    notes = (data.get('notes') or '').strip() or None

    if new_status == 'printing':
        # Fetch print time so we can compute print_end_expected
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

    # ── Failed: retry or send back ────────────────────────────────────────
    if new_status == 'failed':
        attempt = job.get('attempt_number') or 1
        MAX_ATTEMPTS = 3

        if attempt < MAX_ATTEMPTS:
            # Still have retries left → create a new job on the same printer
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
            # Put request back to queued
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
            # 3rd failure → send back to student
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

    # ── All other statuses: normal mirror ─────────────────────────────────
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

    return jsonify({'success': True, 'message': f'Job status updated to "{new_status}"'}), 200


# ── Operating-hours helper ─────────────────────────────────────────────────────
# Mon=0 10:00-16:00, Tue-Thu=1-3 09:00-17:00, Fri=4 09:00-16:00
_OP_HOURS = {
    0: (10, 16),   # Monday
    1: ( 9, 17),   # Tuesday
    2: ( 9, 17),   # Wednesday
    3: ( 9, 17),   # Thursday
    4: ( 9, 16),   # Friday
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
        return True   # weekend
    _, close_h = _OP_HOURS[wd]
    closing = print_end_dt.replace(hour=close_h, minute=0, second=0, microsecond=0)
    return print_end_dt > closing


@app.route('/api/admin/notifications', methods=['GET'])
def get_staff_notifications():
    """
    Poll endpoint — returns pending notifications for the logged-in staff member.
    Notification types:
      - 'print_done'     : a printing job's print_end_expected has passed
      - 'overschedule'   : print_end_expected exceeds today's closing time
    Marks notified jobs as staff_notified=1 so they aren't repeated.
    """
    from datetime import datetime
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'notifications': []}), 401
    payload = AuthService.verify_jwt_token(auth_header.split(' ')[1])
    if not payload or payload.get('user_type') not in ('admin', 'student_staff'):
        return jsonify({'success': False, 'notifications': []}), 403

    now = datetime.utcnow()

    # All printing jobs that are overdue and not yet notified —
    # any logged-in staff member should see these (not just the one who started it)
    active_jobs = db.fetch_all("""
        SELECT pj.job_id, pj.print_end_expected, pj.staff_notified,
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
    """, ()) or []

    notifications = []
    for job in active_jobs:
        end_dt = job.get('print_end_expected')
        if not end_dt:
            continue
        # end_dt comes from DB as a datetime object (UTC)
        if isinstance(end_dt, str):
            from datetime import datetime as _dt
            end_dt = _dt.fromisoformat(end_dt)

        note = None
        if end_dt <= now:
            note = {
                'type':         'print_done',
                'job_id':       job['job_id'],
                'project_name': job['project_name'],
                'student_name': job.get('student_name') or job['student_email'],
                'printer_name': job.get('printer_name', ''),
                'message':      f"⏰ Print complete: \"{job['project_name']}\" on {job.get('printer_name','')}",
            }
        elif _job_exceeds_hours(end_dt):
            note = {
                'type':         'overschedule',
                'job_id':       job['job_id'],
                'project_name': job['project_name'],
                'student_name': job.get('student_name') or job['student_email'],
                'printer_name': job.get('printer_name', ''),
                'message':      f"⚠️ \"{job['project_name']}\" will exceed today's closing time on {job.get('printer_name','')}",
            }

        if note:
            notifications.append(note)
            db.execute_query(
                "UPDATE print_jobs SET staff_notified = 1 WHERE job_id = %s",
                (job['job_id'],)
            )

    return jsonify({'success': True, 'notifications': notifications}), 200


@app.route('/api/admin/jobs/reorder', methods=['PATCH'])
def reorder_printer_queue(  ):
    """
    Reorder jobs in a printer's queue.
    Body: { printer_id, order: [job_id, job_id, ...] }
    The array defines the new queue_position (index+1).
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


@app.route('/api/admin/jobs/<int:job_id>', methods=['DELETE'])
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

@app.route('/api/admin/printers', methods=['GET'])
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


@app.route('/api/admin/printers', methods=['POST'])
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

    # Check duplicate
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


@app.route('/api/admin/printers/<int:printer_id>', methods=['PATCH'])
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


@app.route('/api/admin/printers/<int:printer_id>', methods=['DELETE'])
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

@app.route('/api/admin/admins', methods=['GET'])
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


@app.route('/api/admin/admins', methods=['POST'])
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
        return jsonify({'success': True, 'message': 'Admin created successfully'}), 201
    return jsonify({'success': False, 'message': 'Failed to create admin'}), 500


@app.route('/api/admin/admins/<path:email>', methods=['DELETE'])
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

    existing = db.fetch_one("SELECT email FROM admins WHERE email = %s", (email,))
    if not existing:
        return jsonify({'success': False, 'message': 'Admin not found'}), 404

    # Clean up related rows
    db.execute_query("DELETE FROM totp_secrets WHERE email = %s AND user_type = 'admin'", (email,))
    db.execute_query("DELETE FROM password_reset_tokens WHERE email = %s AND user_type = 'admin'", (email,))
    db.execute_query("DELETE FROM email_verification_codes WHERE email = %s AND user_type = 'admin'", (email,))
    db.execute_query("DELETE FROM admins WHERE email = %s", (email,))
    return jsonify({'success': True, 'message': 'Admin deleted'}), 200


@app.route('/api/admin/admins/<path:email>/password', methods=['PATCH'])
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


@app.route('/api/admin/print-requests', methods=['GET'])
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
    week = request.args.get('week')        # optional 'YYYY-WW' filter
    from_date = request.args.get('from')   # optional 'YYYY-MM-DD'
    to_date = request.args.get('to')       # optional 'YYYY-MM-DD'

    result = PrintService.get_all_requests(status, priority, week, from_date, to_date)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route('/api/admin/print-requests/<int:request_id>/status', methods=['PATCH'])
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
        change_reason=data.get('change_reason')
    )
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route('/api/admin/print-requests/<int:request_id>/priority', methods=['PATCH'])
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


@app.route('/api/admin/print-requests/<int:request_id>/return', methods=['POST'])
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
    unlocked_fields = data.get('unlocked_fields')  # list or None

    if not reason:
        return jsonify({'success': False, 'message': 'A return reason is required'}), 400

    result = PrintService.return_print_request(
        request_id=request_id,
        admin_email=payload['email'],
        reason=reason,
        unlocked_fields=unlocked_fields,
    )

    if result['success']:
        return jsonify(result), 200
    elif 'not found' in result['message']:
        return jsonify(result), 404
    else:
        return jsonify(result), 400


@app.route('/api/admin/print-requests/<int:request_id>/approve-with-ufp', methods=['POST'])
def admin_approve_with_ufp(request_id):
    """Approve a print request and attach UFP slicer data (Admin only).

    Body JSON:
        ufp_filename          – saved filename in uploads folder (from upload-ufp response)
        ufp_original_name     – original filename uploaded by admin
        ufp_print_time_minutes – total print time in minutes (decimal)
        ufp_material_g        – material weight in grams (decimal)
        admin_notes           – optional text note
    """
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

    # Verify the UFP file actually exists in the uploads folder
    ufp_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(ufp_filename))
    if not os.path.exists(ufp_path):
        return jsonify({'success': False, 'message': 'UFP file not found on server'}), 400

    try:
        # Verify the request exists and is in an approvable state
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

        # Update the record: status + UFP fields
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
                payload['email'],
                request_id
            )
        )

        # Record history
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


@app.route('/api/admin/print-requests/statistics', methods=['GET'])
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


@app.route('/api/2fa/status', methods=['GET'])
def get_2fa_status():
    """Return the 2FA enabled status for the current user."""
    payload = _get_auth_payload()
    if not payload:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    status = TotpService.get_totp_status(payload['email'], payload['user_type'])
    return jsonify({'success': True, **status}), 200


@app.route('/api/2fa/setup', methods=['POST'])
def setup_2fa():
    """
    Generate a new TOTP secret and return a QR code (Base64 PNG).
    The user should scan it with Google Authenticator, Duo, or any TOTP app.
    After scanning, call /api/2fa/confirm with the first displayed code to activate.
    """
    payload = _get_auth_payload()
    if not payload:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    result = TotpService.setup_totp(payload['email'], payload['user_type'])
    return jsonify(result), 200 if result['success'] else 500


@app.route('/api/admin/migrate-totp-enum', methods=['POST'])
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


@app.route('/api/2fa/debug', methods=['GET'])
def debug_2fa():
    """Temporary debug: show server time and expected TOTP code for the current user."""
    import datetime as _dt
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
    now = _dt.datetime.utcnow()
    return jsonify({
        'server_utc': now.isoformat(),
        'server_timestamp': int(now.timestamp()),
        'expected_code': totp.now(),
        'is_active': row['is_active'],
        'user_type_in_jwt': payload['user_type'],
        'email': payload['email'],
    })


@app.route('/api/2fa/confirm', methods=['POST'])
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


@app.route('/api/2fa/verify', methods=['POST'])
def verify_2fa():
    """
    Login step 2: after password verification, submit the TOTP code to obtain a full JWT.
    Body: { "email": "...", "user_type": "student|admin", "code": "123456" }
    Note: this endpoint does not require an Authorization header (the user has no token yet).
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

    # TOTP verified — issue a full JWT
    # If user_type is admin, include the admin role from the database so the
    # frontend and backend can apply role-based permissions (e.g. professor).
    if user_type == 'admin':
        admin_row = db.fetch_one("SELECT role FROM admins WHERE email = %s", (email,))
        role = admin_row.get('role') if admin_row else None
        payload = {
            'email': email,
            'user_type': user_type,
            'role': role,
            'exp': __import__('datetime').datetime.utcnow() + __import__('datetime').timedelta(hours=Config.JWT_EXPIRATION_HOURS),
            'iat': __import__('datetime').datetime.utcnow()
        }
        token = __import__('jwt').encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')
    else:
        token = AuthService.generate_jwt_token(email, user_type)

    return jsonify({
        'success': True,
        'message': '2FA verified successfully',
        'token': token
    }), 200


@app.route('/api/2fa/login-verify', methods=['POST'])
def login_verify_2fa():
    """
    Login step 2 (secure): verify temp_token + TOTP code, then issue a full JWT.
    Body: { "temp_token": "...", "code": "123456" }
    The temp_token is issued after successful password verification; it expires in 5 minutes with scope='2fa_pending'.
    """
    import datetime as _dt
    data = request.json or {}
    temp_token = data.get('temp_token', '').strip()
    code       = data.get('code', '').strip()

    if not temp_token or not code:
        return jsonify({'success': False, 'message': '"temp_token" and "code" are both required'}), 400

    # Decode the temp token
    tp = AuthService.verify_jwt_token(temp_token)
    if not tp or tp.get('scope') != '2fa_pending':
        return jsonify({'success': False, 'message': 'Invalid or expired session — please log in again'}), 401

    email         = tp['email']
    user_type     = tp['user_type']
    effective_type = tp.get('effective_type', user_type)

    # Verify TOTP code
    result = TotpService.verify_totp(email, user_type, code)
    if not result['success']:
        return jsonify({'success': False, 'message': 'Invalid code — please try again'}), 401

    # Issue a full JWT
    if user_type == 'admin':
        role = tp.get('role')
        payload = {
            'email': email,
            'user_type': user_type,
            'role': role,
            'exp': _dt.datetime.utcnow() + _dt.timedelta(hours=Config.JWT_EXPIRATION_HOURS),
            'iat': _dt.datetime.utcnow()
        }
        import jwt as _jwt
        token = _jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')
    else:
        token = AuthService.generate_jwt_token(email, effective_type)

    # Fetch user info to return to the frontend
    table = 'students' if user_type == 'student' else 'admins'
    user_row = db.fetch_one(f"SELECT email, full_name, role FROM {table} WHERE email = %s", (email,))
    user_obj = {
        'email': email,
        'full_name': user_row['full_name'] if user_row else email,
        'user_type': effective_type,
        **({'role': tp.get('role')} if user_type != 'student' else {})
    }

    return jsonify({'success': True, 'token': token, 'user': user_obj}), 200


@app.route('/api/2fa/disable', methods=['DELETE'])
def disable_2fa():
    """Disable 2FA for the current user. Only a valid JWT is required — no TOTP code needed."""
    payload = _get_auth_payload()
    if not payload:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    result = TotpService.disable_totp(payload['email'], payload['user_type'])
    return jsonify(result), 200


@app.route('/api/admin/students/<email>/2fa', methods=['DELETE'])
def admin_reset_student_2fa(email):
    """
    Admin: forcibly clear a specific student's 2FA.
    Requires admin JWT only — no action required from the student.
    """
    payload = _get_auth_payload()
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    result = TotpService.disable_totp(email, 'student')
    return jsonify(result), 200 if result['success'] else 400


# ===========================================================================
# Weekly Report API  (admin only)
# ===========================================================================


@app.route('/api/reports/dashboard', methods=['GET'])
def get_dashboard_report():
    """
    GET /api/reports/dashboard?from=YYYY-MM-DD&to=YYYY-MM-DD
    Return aggregated stats directly from print_requests table.
    Requires admin / professor / manager JWT.
    """
    payload = _get_auth_payload()
    if not payload or payload.get('user_type') not in ('admin', 'professor', 'manager'):
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    from_date = request.args.get('from', '').strip() or None
    to_date   = request.args.get('to',   '').strip() or None

    # Default: last 7 days
    if not from_date or not to_date:
        from datetime import datetime, timedelta
        to_dt   = datetime.utcnow()
        from_dt = to_dt - timedelta(days=7)
        from_date = from_dt.strftime('%Y-%m-%d')
        to_date   = to_dt.strftime('%Y-%m-%d')

    try:
        # Overall summary
        summary = db.fetch_one("""
            SELECT
                COUNT(*) AS total_requests,
                SUM(status = 'completed') AS completed,
                SUM(status = 'in_progress') AS in_progress,
                SUM(status = 'pending') AS pending,
                SUM(status = 'approved') AS approved,
                SUM(status = 'rejected') AS rejected,
                SUM(status = 'cancelled') AS cancelled,
                ROUND(SUM(slicer_time_minutes) / 60, 1) AS total_print_hours,
                ROUND(SUM(slicer_material_g), 1) AS total_material_g,
                COUNT(DISTINCT student_email) AS unique_students
            FROM print_requests
            WHERE DATE(created_at) BETWEEN %s AND %s
        """, (from_date, to_date))

        # By material type
        by_material = db.fetch_all("""
            SELECT material_type, COUNT(*) AS count,
                   ROUND(SUM(slicer_material_g), 1) AS material_g
            FROM print_requests
            WHERE DATE(created_at) BETWEEN %s AND %s
            GROUP BY material_type
            ORDER BY count DESC
        """, (from_date, to_date))

        # By status over time (daily)
        by_day = db.fetch_all("""
            SELECT DATE(created_at) AS day, COUNT(*) AS count,
                   SUM(status = 'completed') AS completed
            FROM print_requests
            WHERE DATE(created_at) BETWEEN %s AND %s
            GROUP BY DATE(created_at)
            ORDER BY day
        """, (from_date, to_date))

        # Top students
        top_students = db.fetch_all("""
            SELECT pr.student_email, s.full_name,
                   COUNT(*) AS request_count,
                   SUM(pr.status = 'completed') AS completed
            FROM print_requests pr
            LEFT JOIN students s ON pr.student_email = s.email
            WHERE DATE(pr.created_at) BETWEEN %s AND %s
            GROUP BY pr.student_email, s.full_name
            ORDER BY request_count DESC
            LIMIT 10
        """, (from_date, to_date))

        # Recent completed requests
        recent = db.fetch_all("""
            SELECT pr.request_id, pr.student_email, s.full_name,
                   pr.project_name, pr.material_type,
                   pr.slicer_time_minutes, pr.slicer_material_g,
                   pr.status, pr.created_at, pr.completed_at
            FROM print_requests pr
            LEFT JOIN students s ON pr.student_email = s.email
            WHERE DATE(pr.created_at) BETWEEN %s AND %s
            ORDER BY pr.created_at DESC
            LIMIT 50
        """, (from_date, to_date))

        # Convert datetime objects to strings for JSON
        def serialize(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            return obj

        recent_list = []
        for r in recent:
            recent_list.append({k: serialize(v) for k, v in r.items()})

        by_day_list = []
        for r in by_day:
            by_day_list.append({k: serialize(v) for k, v in r.items()})

        return jsonify({
            'success': True,
            'period': {'from': from_date, 'to': to_date},
            'summary': summary,
            'by_material': by_material,
            'by_day': by_day_list,
            'top_students': top_students,
            'recent': recent_list,
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Report error: {str(e)}'}), 500


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'message': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print("Starting DGSpace Backend Server...")
    print(f"Database: {Config.DB_NAME}")
    print(f"Server running on: http://localhost:{port}")
    
    # Connect to database
    db.connect()
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True
    )

