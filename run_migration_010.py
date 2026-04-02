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
    cur.execute(
        "ALTER TABLE print_requests "
        "ADD COLUMN revision_fields VARCHAR(255) DEFAULT NULL "
        "COMMENT 'JSON array of fields unlocked for student resubmit, set by staff on send-back'"
    )
    print("✅  Column 'revision_fields' added to print_requests")
except Exception as e:
    print(f"⚠️   Column may already exist: {e}")

conn.commit()
cur.close()
conn.close()
print("Done.")
