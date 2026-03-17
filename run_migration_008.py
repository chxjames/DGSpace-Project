import pymysql
from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', '.env'))

conn = pymysql.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    port=int(os.getenv('DB_PORT', 3306)),
    user=os.getenv('DB_USER', 'dgspace_user'),
    password=os.getenv('DB_PASSWORD', ''),
    database=os.getenv('DB_NAME', 'DGSpace'),
)
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE students ADD COLUMN role ENUM('student','student_staff') NOT NULL DEFAULT 'student' AFTER department")
    print("✅ Column 'role' added")
except Exception as e:
    print(f"⚠️  Column may already exist: {e}")

try:
    cur.execute("CREATE INDEX idx_students_role ON students (role)")
    print("✅ Index created")
except Exception as e:
    print(f"⚠️  Index may already exist: {e}")

conn.commit()
cur.close()
conn.close()
print("Done.")
