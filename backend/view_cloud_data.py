"""View data in cloud database"""
import mysql.connector
from config import Config

try:
    conn = mysql.connector.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        ssl_disabled=False
    )
    
    cursor = conn.cursor(dictionary=True)
    
    print("=" * 70)
    print("☁️  CLOUD DATABASE CONTENTS")
    print("=" * 70)
    print()
    
    # Students
    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()
    print(f"👨‍🎓 STUDENTS ({len(students)} total):")
    if students:
        for student in students:
            print(f"  - {student['email']}: {student['full_name']}")
    else:
        print("  (No students yet)")
    print()
    
    # Admins
    cursor.execute("SELECT * FROM admins")
    admins = cursor.fetchall()
    print(f"👤 ADMINS ({len(admins)} total):")
    if admins:
        for admin in admins:
            print(f"  - {admin['email']}: {admin['full_name']} (Role: {admin['role']})")
    else:
        print("  (No admins yet)")
    print()
    
    # Email verification codes
    cursor.execute("SELECT COUNT(*) as count FROM email_verification_codes")
    email_count = cursor.fetchone()['count']
    print(f"📧 EMAIL VERIFICATION CODES: {email_count}")
    
    # Password reset tokens
    cursor.execute("SELECT COUNT(*) as count FROM password_reset_tokens")
    token_count = cursor.fetchone()['count']
    print(f"🔑 PASSWORD RESET TOKENS: {token_count}")
    
    print()
    print("=" * 70)
    print("✅ Your partner can access this data with:")
    print(f"   Host: {Config.DB_HOST}")
    print(f"   Port: {Config.DB_PORT}")
    print(f"   User: {Config.DB_USER}")
    print(f"   Database: {Config.DB_NAME}")
    print("=" * 70)
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
