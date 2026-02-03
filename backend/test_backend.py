"""
Test script to verify database connection and basic functionality
Run this before starting the server to test everything
"""

from database import db
from auth_service import AuthService

def test_database_connection():
    """Test database connection"""
    print("\n🔍 Testing Database Connection...")
    connection = db.connect()
    if connection:
        print("✅ Database connection successful!")
        return True
    else:
        print("❌ Database connection failed!")
        return False

def test_tables_exist():
    """Check if all required tables exist"""
    print("\n🔍 Checking Database Tables...")
    
    tables = ['students', 'admins', 'email_verification_codes', 'password_reset_tokens']
    
    for table in tables:
        result = db.fetch_one(f"SHOW TABLES LIKE '{table}'")
        if result:
            print(f"✅ Table '{table}' exists")
        else:
            print(f"❌ Table '{table}' missing!")
            return False
    
    return True

def test_password_hashing():
    """Test password hashing"""
    print("\n🔍 Testing Password Hashing...")
    
    password = "TestPassword123!"
    hashed = AuthService.hash_password(password)
    
    print(f"Original: {password}")
    print(f"Hashed: {hashed[:50]}...")
    
    # Test verification
    if AuthService.verify_password(password, hashed):
        print("✅ Password hashing works!")
        return True
    else:
        print("❌ Password verification failed!")
        return False

def test_verification_code():
    """Test verification code generation"""
    print("\n🔍 Testing Verification Code Generation...")
    
    code = AuthService.generate_verification_code()
    print(f"Generated code: {code}")
    
    if len(code) == 6 and code.isdigit():
        print("✅ Verification code generation works!")
        return True
    else:
        print("❌ Verification code generation failed!")
        return False

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("🧪 RUNNING BACKEND TESTS")
    print("=" * 60)
    
    tests = [
        test_database_connection,
        test_tables_exist,
        test_password_hashing,
        test_verification_code
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ ALL TESTS PASSED!")
        print("🚀 Backend is ready to run!")
    else:
        print("❌ SOME TESTS FAILED!")
        print("⚠️  Please fix the issues before running the server")
    print("=" * 60)
    
    # Cleanup
    db.disconnect()

if __name__ == "__main__":
    run_all_tests()
