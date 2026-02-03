"""
Quick script to add admin to database
"""
from database import db
from auth_service import AuthService

# Connect to database
db.connect()

# Admin details
email = "chenghaoxu@sandiego.edu"
full_name = "Chenghao Xu"
password = "Admin123!"  # Temporary password - they should change it
role = "super_admin"  # or "admin" or "moderator"

# Register admin
result = AuthService.register_admin(email, password, full_name, role)

if result['success']:
    print(f"✅ {result['message']}")
    print(f"\n📧 Email: {email}")
    print(f"🔑 Temporary Password: {password}")
    print(f"👤 Full Name: {full_name}")
    print(f"⭐ Role: {role}")
    
    # Option 1: Auto-verify (no email needed) - CURRENT METHOD
    db.execute_query("UPDATE admins SET email_verified = TRUE WHERE email = %s", (email,))
    print("✅ Email marked as verified - admin can login immediately!")
    
    # Option 2: Send verification email (uncomment to use)
    # from email_service import EmailService
    # code_result = AuthService.create_verification_code(email, 'admin')
    # if code_result['success']:
    #     EmailService.send_verification_email(email, code_result['code'], full_name)
    #     print("📧 Verification email sent!")
else:
    print(f"❌ {result['message']}")

db.disconnect()
