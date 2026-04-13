"""
run_migration_015.py
--------------------
Drops the FK constraint on print_requests.student_email so that admins
(whose emails live in the `admins` table, not `students`) can submit print requests.

Usage:
    cd backend
    python ../run_migration_015.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from database import db

def run():
    print("=== Migration 015: Drop FK on print_requests.student_email ===")

    # Find the constraint name dynamically
    row = db.fetch_one(
        """
        SELECT CONSTRAINT_NAME
        FROM   information_schema.KEY_COLUMN_USAGE
        WHERE  TABLE_SCHEMA          = DATABASE()
          AND  TABLE_NAME            = 'print_requests'
          AND  COLUMN_NAME           = 'student_email'
          AND  REFERENCED_TABLE_NAME IS NOT NULL
        LIMIT 1
        """, ()
    )

    if not row or not row.get('CONSTRAINT_NAME'):
        print("No FK found on print_requests.student_email — already dropped or never existed.")
        print("Migration 015 complete (no-op).")
        return

    constraint = row['CONSTRAINT_NAME']
    print(f"Found FK constraint: {constraint}")
    print(f"Dropping FK `{constraint}` from print_requests ...")

    db.execute_query(f"ALTER TABLE print_requests DROP FOREIGN KEY `{constraint}`", ())

    print(f"✅ FK `{constraint}` dropped successfully.")
    print("Migration 015 complete.")

if __name__ == '__main__':
    run()
