import sys
sys.path.insert(0, r'e:\DGSpace-Project-1\backend')
from database import db
db.connect()

# Step 1: Add role column
try:
    db.execute_query(
        "ALTER TABLE students ADD COLUMN role ENUM('student','student_staff') NOT NULL DEFAULT 'student' AFTER department"
    )
    print("SUCCESS: role column added")
except Exception as e:
    print(f"SKIP/ERROR (column): {e}")

# Step 2: Add index
try:
    db.execute_query("CREATE INDEX idx_students_role ON students (role)")
    print("SUCCESS: index created")
except Exception as e:
    print(f"SKIP/ERROR (index): {e}")

# Verify
rows = db.fetch_all("SELECT email, role FROM students LIMIT 5")
print("Current students:", rows)
