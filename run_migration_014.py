"""
Migration 014 — add print_end_expected and staff_notified to print_jobs
Run once against the Railway MySQL database.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from database import db

db.connect()

columns = [
    ("print_end_expected", "ALTER TABLE print_jobs ADD COLUMN print_end_expected DATETIME NULL AFTER started_at"),
    ("staff_notified",     "ALTER TABLE print_jobs ADD COLUMN staff_notified TINYINT NOT NULL DEFAULT 0 AFTER print_end_expected"),
]

for col_name, ddl in columns:
    try:
        db.execute_query(ddl)
        print(f"✅  {col_name} added.")
    except Exception as e:
        if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
            print(f"ℹ️   {col_name} already exists — skipped.")
        else:
            print(f"❌  {col_name}: {e}")

print("Migration 014 done.")
