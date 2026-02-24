from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from database import db
from auth_service import AuthService
from email_service import EmailService, mail
from config import Config
from print_service import PrintService
from totp_service import TotpService
from stl_analysis import analyze_stl
import os
import uuid

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


# ==================== 3D PRINT REQUEST ENDPOINTS ====================

@app.route('/api/print-requests/upload-stl', methods=['POST'])
def upload_stl():
    """Upload a .stl file before submitting a print request (Student)"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') != 'student':
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

    # Analyze the STL file for volume, weight, and print time estimates
    material = request.form.get('material', 'PLA')
    try:
        infill = float(request.form.get('infill', 0.20))
        infill = max(0.01, min(1.0, infill))   # clamp to valid range
    except (ValueError, TypeError):
        infill = 0.20
    analysis = analyze_stl(save_path, material=material, infill=infill)

    response = {
        'success': True,
        'filename': saved_name,
        'original_name': original_name
    }

    if analysis.get('success'):
        response['analysis'] = {
            'volume_cm3':                analysis['volume_cm3'],
            'bounding_box':              analysis['bounding_box'],
            'estimated_weight_grams':    analysis['estimated_weight_grams'],
            'estimated_print_time_hours': analysis['estimated_print_time_hours'],
            'material':                  analysis['material'],
            'infill_percent':            analysis['infill_percent'],
        }

    return jsonify(response), 201


@app.route('/api/print-requests/upload-stl/<filename>', methods=['DELETE'])
def delete_uploaded_stl(filename: str):
    """Delete a previously uploaded STL file before submitting a print request (Student)

    This supports the frontend "Remove" button so mistaken uploads don't linger on disk.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload or payload.get('user_type') != 'student':
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


@app.route('/api/uploads/<filename>', methods=['GET'])
def serve_upload(filename: str):
    """Serve uploaded STL files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/api/print-requests/analyze-stl/<filename>', methods=['GET'])
def analyze_stl_file(filename: str):
    """Analyze an uploaded STL file and return volume / weight / time estimates."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload:
        return jsonify({'success': False, 'message': 'Invalid or expired token'}), 401

    safe_name = os.path.basename(filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)

    material = request.args.get('material', 'PLA')
    try:
        infill = float(request.args.get('infill', 0.20))
        infill = max(0.01, min(1.0, infill))
    except (ValueError, TypeError):
        infill = 0.20
    analysis = analyze_stl(file_path, material=material, infill=infill)

    if not analysis.get('success'):
        return jsonify(analysis), 400

    return jsonify({'success': True, 'analysis': analysis}), 200


@app.route('/api/print-requests', methods=['POST'])
def create_print_request():
    """Create a new 3D print request (Student)"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    
    if not payload or payload.get('user_type') != 'student':
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
        estimated_weight_grams=data.get('estimated_weight_grams'),
        estimated_print_time_hours=data.get('estimated_print_time_hours'),
        priority=data.get('priority', 'normal'),
        stl_file_path=data.get('stl_file_path'),
        stl_original_name=data.get('stl_original_name')
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
    
    if not payload or payload.get('user_type') != 'student':
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

    if payload.get('user_type') != 'student':
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
        SELECT email, full_name, department, email_verified, created_at, last_login
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

@app.route('/api/admin/print-requests', methods=['GET'])
def admin_get_all_requests():
    """Get all print requests (Admin only)"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    
    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    status = request.args.get('status')
    priority = request.args.get('priority')
    
    result = PrintService.get_all_requests(status, priority)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route('/api/admin/print-requests/<int:request_id>/status', methods=['PATCH'])
def admin_update_request_status(request_id):
    """Update the status of a print request (Admin only)"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    
    if not payload or payload.get('user_type') != 'admin':
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
    """Return a print request back to the student for revision (Admin only)"""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)

    if not payload or payload.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    data = request.json or {}
    reason = data.get('reason', '').strip()

    if not reason:
        return jsonify({'success': False, 'message': 'A return reason is required'}), 400

    result = PrintService.return_print_request(
        request_id=request_id,
        admin_email=payload['email'],
        reason=reason
    )

    if result['success']:
        return jsonify(result), 200
    elif 'not found' in result['message']:
        return jsonify(result), 404
    else:
        return jsonify(result), 400


@app.route('/api/admin/print-requests/statistics', methods=['GET'])
def admin_get_statistics():
    """Get print request statistics (Admin only)"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401
    
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    
    if not payload or payload.get('user_type') != 'admin':
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
    token = AuthService.generate_jwt_token(email, user_type)
    return jsonify({
        'success': True,
        'message': '2FA 验证通过',
        'token': token
    }), 200


@app.route('/api/2fa/disable', methods=['DELETE'])
def disable_2fa():
    """
    关闭 2FA。需要在 body 中提供当前 TOTP 验证码以确认身份。
    Body: { "code": "123456" }
    """
    payload = _get_auth_payload()
    if not payload:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.json or {}
    code = data.get('code', '').strip()
    if not code:
        return jsonify({'success': False, 'message': '请提供当前 TOTP 验证码'}), 400

    # 先验证码正确再删除，防止误操作
    verify = TotpService.verify_totp(payload['email'], payload['user_type'], code)
    if not verify['success']:
        return jsonify({'success': False, 'message': '验证码错误，无法关闭 2FA'}), 400

    result = TotpService.disable_totp(payload['email'], payload['user_type'])
    return jsonify(result), 200


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'message': 'Internal server error'}), 500

if __name__ == '__main__':
    print("Starting DGSpace Backend Server...")
    print(f"Database: {Config.DB_NAME}")
    print(f"Server running on: http://localhost:{Config.PORT or 5000}")
    
    # Connect to database
    db.connect()
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=int(Config.PORT or 5000),
        debug=True
    )

