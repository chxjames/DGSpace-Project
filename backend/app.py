from flask import Flask, request, jsonify
from flask_cors import CORS
from database import db
from auth_service import AuthService
from email_service import EmailService, mail
from config import Config

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

# Configure Flask-Mail
app.config['MAIL_SERVER'] = Config.MAIL_SERVER
app.config['MAIL_PORT'] = Config.MAIL_PORT
app.config['MAIL_USE_TLS'] = Config.MAIL_USE_TLS
app.config['MAIL_USERNAME'] = Config.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = Config.MAIL_PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = Config.MAIL_DEFAULT_SENDER

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
            # Send verification email
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

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'message': 'Internal server error'}), 500

if __name__ == '__main__':
    print("🚀 Starting DGSpace Backend Server...")
    print(f"📊 Database: {Config.DB_NAME}")
    print(f"🌐 Server running on: http://localhost:{Config.PORT or 5000}")
    
    # Connect to database
    db.connect()
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=int(Config.PORT or 5000),
        debug=True
    )
