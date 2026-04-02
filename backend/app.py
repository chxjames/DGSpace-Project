from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from database import db
from auth_service import AuthService
from email_service import EmailService, mail
from config import Config
from print_service import PrintService
from totp_service import TotpService
from ufp_analysis import analyze_ufp
import os
import uuid
import bcrypt

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

# Configure Flask-Mail
app.config['MAIL_SERVER'] = Config.MAIL_SERVER
app.config['MAIL_PORT'] = Config.MAIL_PORT
app.config['MAIL_USE_TLS'] = Config.MAIL_USE_TLS
app.config['MAIL_USERNAME'] = Config.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = Config.MAIL_PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = Config.MAIL_DEFAULT_SENDER

# Configure upload folder
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

mail.init_app(app)

# Connect to database on startup
@app.before_request
def before_request():
    if not db.connection or not db.connection.is_connected():
        db.connect()
    # Auto-cleanup: delete unverified accounts older than 10 minutes
    try:
        db.execute_query(
            "DELETE FROM email_verification_codes WHERE is_used = FALSE AND expires_at < NOW() AND email IN (SELECT email FROM students WHERE email_verified = FALSE)"
        )
        db.execute_query(
            "DELETE FROM students WHERE email_verified = FALSE AND created_at < DATE_SUB(NOW(), INTERVAL 10 MINUTE)"
        )
    except Exception:
        pass

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
    
    if not payload or payload.get('user_type') not in ('student', 'student_staff'):
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
    """从 Authorization header 解析 JWT payload，可选校验 user_type"""
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
    """查询当前用户的 2FA 启用状态"""
    payload = _get_auth_payload()
    if not payload:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    status = TotpService.get_totp_status(payload['email'], payload['user_type'])
    return jsonify({'success': True, **status}), 200


@app.route('/api/2fa/setup', methods=['POST'])
def setup_2fa():
    """
    生成新的 TOTP 密钥并返回二维码（Base64 PNG）。
    用户需要用 Google Authenticator / Duo / 任意 TOTP 应用扫码。
    扫码后调用 /api/2fa/confirm 提交第一个验证码以激活。
    """
    payload = _get_auth_payload()
    if not payload:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    result = TotpService.setup_totp(payload['email'], payload['user_type'])
    return jsonify(result), 200 if result['success'] else 500


@app.route('/api/2fa/confirm', methods=['POST'])
def confirm_2fa():
    """
    用户扫码后，提交 TOTP 应用显示的 6 位验证码来激活 2FA。
    Body: { "code": "123456" }
    """
    payload = _get_auth_payload()
    if not payload:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.json or {}
    code = data.get('code', '').strip()
    if not code:
        return jsonify({'success': False, 'message': 'code 字段不能为空'}), 400

    result = TotpService.confirm_totp(payload['email'], payload['user_type'], code)
    return jsonify(result), 200 if result['success'] else 400


@app.route('/api/2fa/verify', methods=['POST'])
def verify_2fa():
    """
    登录第二步：密码验证通过后，前端提交 TOTP 验证码获取正式 JWT。
    Body: { "email": "...", "user_type": "student|admin", "code": "123456" }
    注意：此端点不需要 Authorization header（用户还未拿到正式 token）。
    """
    data = request.json or {}
    email = data.get('email', '').strip()
    user_type = data.get('user_type', 'student')
    code = data.get('code', '').strip()

    if not email or not code:
        return jsonify({'success': False, 'message': 'email 和 code 均为必填项'}), 400

    result = TotpService.verify_totp(email, user_type, code)
    if not result['success']:
        return jsonify(result), 401

    # TOTP 验证通过，颁发正式 JWT
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
        'message': '2FA 验证通过',
        'token': token
    }), 200


@app.route('/api/2fa/login-verify', methods=['POST'])
def login_verify_2fa():
    """
    登录第二步（安全版）：验证 temp_token + TOTP 码，通过后颁发正式 JWT。
    Body: { "temp_token": "...", "code": "123456" }
    temp_token 由密码验证成功后服务端签发，有效期 5 分钟，scope='2fa_pending'。
    """
    import datetime as _dt
    data = request.json or {}
    temp_token = data.get('temp_token', '').strip()
    code       = data.get('code', '').strip()

    if not temp_token or not code:
        return jsonify({'success': False, 'message': 'temp_token 和 code 均为必填项'}), 400

    # 解码 temp token
    tp = AuthService.verify_jwt_token(temp_token)
    if not tp or tp.get('scope') != '2fa_pending':
        return jsonify({'success': False, 'message': '无效或已过期的会话，请重新登录'}), 401

    email         = tp['email']
    user_type     = tp['user_type']
    effective_type = tp.get('effective_type', user_type)

    # 验证 TOTP 码
    result = TotpService.verify_totp(email, user_type, code)
    if not result['success']:
        return jsonify({'success': False, 'message': '验证码错误，请重试'}), 401

    # 颁发正式 JWT
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

    # 查询用户信息以返回给前端
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
    """
    关闭自己的 2FA。只需有效 JWT，无需再提交 TOTP 验证码。
    """
    payload = _get_auth_payload()
    if not payload:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    result = TotpService.disable_totp(payload['email'], payload['user_type'])
    return jsonify(result), 200


@app.route('/api/admin/students/<email>/2fa', methods=['DELETE'])
def admin_reset_student_2fa(email):
    """
    管理员强制清除指定学生的 2FA。
    仅需 admin JWT，无需学生本人操作。
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

