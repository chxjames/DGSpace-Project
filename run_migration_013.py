"""Run migration 013 — adds attempt_number to print_jobs."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from database import db

def run():
    db.connect()
    cur = db.connection.cursor()
    try:
        cur.execute("ALTER TABLE print_jobs ADD COLUMN attempt_number TINYINT NOT NULL DEFAULT 1")
        db.connection.commit()
        print("✅ attempt_number column added to print_jobs")
    except Exception as e:
        if '1060' in str(e) or 'Duplicate column' in str(e):
            print("ℹ️  attempt_number already exists — skipped")
        else:
            raise
    finally:
        cur.close()
    print("Migration 013 complete.")

if __name__ == '__main__':
    run()
