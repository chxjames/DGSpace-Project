from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from database import db
from auth_service import AuthService
from email_service import EmailService, mail
from config import Config
from print_service import PrintService
from totp_service import TotpService
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

    return jsonify({
        'success': True,
        'filename': saved_name,
        'original_name': original_name
    }), 201


@app.route('/api/uploads/<filename>', methods=['GET'])
def serve_upload(filename):
    """Serve uploaded STL files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


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
    
    valid_statuses = ['approved', 'rejected', 'in_progress', 'completed', 'cancelled']
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

