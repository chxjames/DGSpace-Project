"""Run migration 012 — adds file_deleted flag to print_requests."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from database import db

def run():
    db.connect()
    cur = db.connection.cursor()

    # Add file_deleted column (idempotent: skip if already exists)
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME   = 'print_requests'
          AND COLUMN_NAME  = 'file_deleted'
    """)
    if cur.fetchone()[0] == 0:
        cur.execute("""
            ALTER TABLE print_requests
              ADD COLUMN file_deleted TINYINT(1) NOT NULL DEFAULT 0
        """)
        print("✅ file_deleted column added to print_requests")
    else:
        print("ℹ️  file_deleted column already exists — skipped")

    # Index (ignore if already exists)
    try:
        cur.execute("""
            CREATE INDEX idx_pr_file_cleanup
              ON print_requests (status, file_deleted, updated_at)
        """)
        print("✅ idx_pr_file_cleanup index created")
    except Exception as e:
        print(f"ℹ️  Index skipped ({e})")

    db.connection.commit()
    cur.close()
    print("Migration 012 complete.")

if __name__ == '__main__':
    run()
