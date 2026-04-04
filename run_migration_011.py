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

# Step 1: extend print_requests.status ENUM
try:
    cur.execute("""
        ALTER TABLE print_requests
        MODIFY COLUMN status ENUM(
            'pending',
            'revision_requested',
            'approved',
            'queued',
            'printing',
            'completed',
            'failed',
            'rejected',
            'cancelled',
            'in_progress'
        ) NOT NULL DEFAULT 'pending'
    """)
    print("✅  print_requests.status ENUM extended")
except Exception as e:
    print(f"⚠️   status ENUM: {e}")

# Step 2: create print_jobs table
try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS print_jobs (
            job_id          INT AUTO_INCREMENT PRIMARY KEY,
            request_id      INT          NOT NULL,
            printer_id      INT          NOT NULL,
            queue_position  INT          NOT NULL DEFAULT 1,
            status          ENUM(
                'queued',
                'file_transferred',
                'printing',
                'completed',
                'failed',
                'cancelled'
            ) NOT NULL DEFAULT 'queued',
            assigned_by     VARCHAR(100) NOT NULL,
            assigned_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            estimated_start DATETIME     NULL,
            estimated_end   DATETIME     NULL,
            started_at      TIMESTAMP    NULL,
            completed_at    TIMESTAMP    NULL,
            notes           TEXT         NULL,

            FOREIGN KEY (request_id) REFERENCES print_requests(request_id) ON DELETE CASCADE,
            FOREIGN KEY (printer_id) REFERENCES printers(printer_id)       ON DELETE RESTRICT,

            INDEX idx_printer_queue  (printer_id, status, queue_position),
            INDEX idx_request_id     (request_id),
            INDEX idx_status         (status),
            INDEX idx_assigned_at    (assigned_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    print("✅  print_jobs table created")
except Exception as e:
    print(f"⚠️   print_jobs table: {e}")

conn.commit()
cur.close()
conn.close()
print("Done.")
