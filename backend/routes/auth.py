import threading
import bcrypt
from flask import Blueprint, request, jsonify
from database import db
from auth_service import AuthService
from email_service import EmailService
from config import Config

auth_bp = Blueprint('auth', __name__)


# ==================== STUDENT ENDPOINTS ====================

@auth_bp.route('/api/students/register', methods=['POST'])
def register_student():
    """Register a new student"""
    data = request.json

    required_fields = ['email', 'password', 'full_name']
    if not all(field in data for field in required_fields):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    if not data['email'].lower().endswith('@sandiego.edu'):
        return jsonify({'success': False, 'message': 'Only @sandiego.edu email addresses are allowed to register.'}), 400

    result = AuthService.register_student(
        email=data['email'],
        password=data['password'],
        full_name=data['full_name'],
        department=data.get('department')
    )

    if result['success']:
        code_result = AuthService.create_verification_code(data['email'], 'student')

        if code_result['success']:
            if Config.DEV_EMAIL_MODE:
                print(f"[DEV] Verification code for {data['email']}: {code_result['code']}")
            else:
                threading.Thread(
                    target=EmailService.send_verification_email,
                    args=(data['email'], code_result['code'], data['full_name']),
                    daemon=True
                ).start()
            return jsonify({
                'success': True,
                'message': 'Registration successful! Please check your email for verification code.'
            }), 201
        else:
            return jsonify(result), 500
    else:
        return jsonify(result), 400


@auth_bp.route('/api/students/verify-email', methods=['POST'])
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


@auth_bp.route('/api/students/login', methods=['POST'])
def login_student():
    """Student login"""
    data = request.json

    if not all(field in data for field in ['email', 'password']):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    if not data['email'].lower().endswith('@sandiego.edu'):
        return jsonify({'success': False, 'message': 'Only @sandiego.edu email addresses are allowed to log in.'}), 400

    result = AuthService.login(data['email'], data['password'], 'student')

    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 401


@auth_bp.route('/api/students/resend-verification', methods=['POST'])
def resend_student_verification():
    """Resend verification code to student"""
    data = request.json

    if 'email' not in data:
        return jsonify({'success': False, 'message': 'Email is required'}), 400

    student = db.fetch_one("SELECT full_name FROM students WHERE email = %s", (data['email'],))

    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    code_result = AuthService.create_verification_code(data['email'], 'student')

    if code_result['success']:
        threading.Thread(
            target=EmailService.send_verification_email,
            args=(data['email'], code_result['code'], student['full_name']),
            daemon=True
        ).start()
        return jsonify({'success': True, 'message': 'Verification code sent'}), 200
    else:
        return jsonify({'success': False, 'message': 'Failed to send verification code'}), 500


# ==================== ADMIN ENDPOINTS ====================

@auth_bp.route('/api/admins/register', methods=['POST'])
def register_admin():
    """Register a new admin"""
    data = request.json

    required_fields = ['email', 'password', 'full_name']
    if not all(field in data for field in required_fields):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    result = AuthService.register_admin(
        email=data['email'],
        password=data['password'],
        full_name=data['full_name'],
        role=data.get('role', 'admin')
    )

    if result['success']:
        return jsonify({
            'success': True,
            'message': 'Admin registration successful! You can now log in.'
        }), 201
    else:
        return jsonify(result), 400


@auth_bp.route('/api/admins/verify-email', methods=['POST'])
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


@auth_bp.route('/api/admins/login', methods=['POST'])
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

@auth_bp.route('/api/profile', methods=['GET'])
def get_profile():
    """Get user profile (requires authentication)"""
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'No token provided'}), 401

    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)

    if not payload:
        return jsonify({'success': False, 'message': 'Invalid or expired token'}), 401

    table = 'students' if payload['user_type'] in ('student', 'student_staff') else 'admins'
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


@auth_bp.route('/api/profile/change-password', methods=['POST'])
def change_password():
    """Change the logged-in user's password.
    Body: { "current_password": "...", "new_password": "...", "totp_code": "..." }
    Requires 2FA to be active and the correct TOTP code.
    """
    from totp_service import TotpService

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.json or {}
    current_pw = data.get('current_password', '').strip()
    new_pw     = data.get('new_password', '').strip()
    totp_code  = (data.get('totp_code') or '').strip()

    if not current_pw or not new_pw:
        return jsonify({'success': False, 'message': 'Both password fields are required'}), 400
    if len(new_pw) < 8:
        return jsonify({'success': False, 'message': 'New password must be at least 8 characters'}), 400
    if not totp_code:
        return jsonify({'success': False, 'message': '2FA code is required'}), 400

    # Verify TOTP first
    totp_result = TotpService.verify_totp(payload['email'], payload['user_type'], totp_code)
    if not totp_result.get('success'):
        return jsonify({'success': False, 'message': 'Invalid 2FA code'}), 400

    table = 'students' if payload['user_type'] in ('student', 'student_staff') else 'admins'
    row = db.fetch_one(f"SELECT password_hash FROM {table} WHERE email = %s", (payload['email'],))
    if not row:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    if not bcrypt.checkpw(current_pw.encode(), row['password_hash'].encode()):
        return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400

    new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
    db.execute_query(f"UPDATE {table} SET password_hash = %s WHERE email = %s", (new_hash, payload['email']))
    return jsonify({'success': True, 'message': 'Password updated successfully'}), 200


@auth_bp.route('/api/profile/change-name', methods=['POST'])
def change_name():
    """Change the logged-in user's display name.
    Body: { "new_name": "...", "totp_code": "123456" }
    Requires 2FA to be active and the correct TOTP code.
    """
    from totp_service import TotpService

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    token = auth_header.split(' ')[1]
    payload = AuthService.verify_jwt_token(token)
    if not payload:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data = request.json or {}
    new_name  = (data.get('new_name') or '').strip()
    totp_code = (data.get('totp_code') or '').strip()

    if not new_name:
        return jsonify({'success': False, 'message': 'New name is required'}), 400
    if len(new_name) > 100:
        return jsonify({'success': False, 'message': 'Name is too long (max 100 characters)'}), 400
    if not totp_code:
        return jsonify({'success': False, 'message': '2FA code is required'}), 400

    # Verify TOTP
    totp_result = TotpService.verify_totp(payload['email'], payload['user_type'], totp_code)
    if not totp_result.get('success'):
        return jsonify({'success': False, 'message': 'Invalid 2FA code'}), 400

    table = 'students' if payload['user_type'] in ('student', 'student_staff') else 'admins'
    db.execute_query(f"UPDATE {table} SET full_name = %s WHERE email = %s", (new_name, payload['email']))
    return jsonify({'success': True, 'message': 'Name updated successfully', 'full_name': new_name}), 200
