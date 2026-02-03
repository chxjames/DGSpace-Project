import bcrypt
import jwt
import random
import string
from datetime import datetime, timedelta
from database import db
from config import Config

class AuthService:
    
    @staticmethod
    def hash_password(password):
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password, hashed_password):
        """Verify a password against its hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    
    @staticmethod
    def generate_verification_code():
        """Generate a 6-digit verification code"""
        return ''.join(random.choices(string.digits, k=6))
    
    @staticmethod
    def generate_jwt_token(email, user_type):
        """Generate JWT token for authenticated user"""
        payload = {
            'email': email,
            'user_type': user_type,
            'exp': datetime.utcnow() + timedelta(hours=Config.JWT_EXPIRATION_HOURS),
            'iat': datetime.utcnow()
        }
        token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')
        return token
    
    @staticmethod
    def verify_jwt_token(token):
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @staticmethod
    def register_student(email, password, full_name, department=None):
        """Register a new student"""
        # Check if email already exists
        existing = db.fetch_one("SELECT email FROM students WHERE email = %s", (email,))
        if existing:
            return {'success': False, 'message': 'Email already registered'}
        
        # Hash password
        password_hash = AuthService.hash_password(password)
        
        # Insert new student
        query = """
            INSERT INTO students (email, password_hash, full_name, department, email_verified)
            VALUES (%s, %s, %s, %s, FALSE)
        """
        result = db.execute_query(query, (email, password_hash, full_name, department))
        
        if result is not None:
            return {'success': True, 'message': 'Student registered successfully'}
        else:
            return {'success': False, 'message': 'Registration failed'}
    
    @staticmethod
    def register_admin(email, password, full_name, role='admin'):
        """Register a new admin"""
        # Check if email already exists
        existing = db.fetch_one("SELECT email FROM admins WHERE email = %s", (email,))
        if existing:
            return {'success': False, 'message': 'Email already registered'}
        
        # Hash password
        password_hash = AuthService.hash_password(password)
        
        # Insert new admin
        query = """
            INSERT INTO admins (email, password_hash, full_name, role, email_verified)
            VALUES (%s, %s, %s, %s, FALSE)
        """
        result = db.execute_query(query, (email, password_hash, full_name, role))
        
        if result is not None:
            return {'success': True, 'message': 'Admin registered successfully'}
        else:
            return {'success': False, 'message': 'Registration failed'}
    
    @staticmethod
    def login(email, password, user_type='student'):
        """Login user and return JWT token"""
        # Determine which table to query
        table = 'students' if user_type == 'student' else 'admins'
        
        # Fetch user
        query = f"SELECT email, password_hash, full_name, email_verified FROM {table} WHERE email = %s"
        user = db.fetch_one(query, (email,))
        
        if not user:
            return {'success': False, 'message': 'Invalid email or password'}
        
        # Verify password
        if not AuthService.verify_password(password, user['password_hash']):
            return {'success': False, 'message': 'Invalid email or password'}
        
        # Check if email is verified
        if not user['email_verified']:
            return {'success': False, 'message': 'Please verify your email first'}
        
        # Update last login
        update_query = f"UPDATE {table} SET last_login = NOW() WHERE email = %s"
        db.execute_query(update_query, (email,))
        
        # Generate JWT token
        token = AuthService.generate_jwt_token(email, user_type)
        
        return {
            'success': True,
            'message': 'Login successful',
            'token': token,
            'user': {
                'email': user['email'],
                'full_name': user['full_name'],
                'user_type': user_type
            }
        }
    
    @staticmethod
    def create_verification_code(email, user_type):
        """Create and store email verification code"""
        code = AuthService.generate_verification_code()
        expires_at = datetime.now() + timedelta(minutes=Config.VERIFICATION_CODE_EXPIRATION_MINUTES)
        
        # Delete any existing codes for this email
        db.execute_query(
            "DELETE FROM email_verification_codes WHERE email = %s AND user_type = %s",
            (email, user_type)
        )
        
        # Insert new code
        query = """
            INSERT INTO email_verification_codes (email, user_type, verification_code, expires_at)
            VALUES (%s, %s, %s, %s)
        """
        result = db.execute_query(query, (email, user_type, code, expires_at))
        
        if result is not None:
            return {'success': True, 'code': code}
        else:
            return {'success': False, 'message': 'Failed to create verification code'}
    
    @staticmethod
    def verify_email_code(email, user_type, code):
        """Verify email using verification code"""
        # Check if code exists and is valid
        query = """
            SELECT * FROM email_verification_codes 
            WHERE email = %s AND user_type = %s AND verification_code = %s 
            AND expires_at > NOW() AND is_used = FALSE
        """
        result = db.fetch_one(query, (email, user_type, code))
        
        if not result:
            return {'success': False, 'message': 'Invalid or expired verification code'}
        
        # Mark code as used
        db.execute_query(
            "UPDATE email_verification_codes SET is_used = TRUE WHERE email = %s AND user_type = %s",
            (email, user_type)
        )
        
        # Update user email_verified status
        table = 'students' if user_type == 'student' else 'admins'
        db.execute_query(
            f"UPDATE {table} SET email_verified = TRUE WHERE email = %s",
            (email,)
        )
        
        return {'success': True, 'message': 'Email verified successfully'}
