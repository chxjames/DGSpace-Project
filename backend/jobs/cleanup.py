import os
import threading
from database import db
from config import Config


def _cleanup_old_files():
    """
    Runs every 24 h in a background daemon thread.
    - UFP + STL: purge for completed/failed/revision_requested/cancelled/rejected
    Sets file_deleted = 1 so record stays in DB.
    """
    try:
        upload_dir = Config.UPLOAD_FOLDER

        # Batch 1: terminal statuses — delete both UFP and STL
        eligible = db.fetch_all(
            """
            SELECT request_id, ufp_file_path, stl_file_path
            FROM   print_requests
            WHERE  file_deleted = 0
              AND  (ufp_file_path IS NOT NULL OR stl_file_path IS NOT NULL)
              AND  status IN ('completed', 'failed', 'revision_requested', 'cancelled', 'rejected')
            """, ()
        )
        purged = 0
        for row in (eligible or []):
            for col in ('ufp_file_path', 'stl_file_path'):
                path = row.get(col)
                if path:
                    full_path = os.path.join(upload_dir, os.path.basename(path))
                    try:
                        if os.path.exists(full_path):
                            os.remove(full_path)
                    except Exception:
                        pass
            db.execute_query(
                "UPDATE print_requests SET file_deleted=1, ufp_file_path=NULL, stl_file_path=NULL WHERE request_id=%s",
                (row['request_id'],)
            )
            purged += 1
        print(f"[cleanup] Terminal purge — {purged} record(s).")

        # Batch 2: active statuses (approved/queued/printing) — keep both STL and UFP
        print(f"[cleanup] Active requests skipped — STL and UFP retained.")

    except Exception as e:
        print(f"[cleanup] Error: {e}")


def _cleanup_unverified():
    """Delete unverified accounts/codes older than 5 minutes."""
    try:
        db.execute_query(
            "DELETE FROM email_verification_codes "
            "WHERE is_used = FALSE AND expires_at < NOW() "
            "AND email IN (SELECT email FROM students WHERE email_verified = FALSE)"
        )
        db.execute_query(
            "DELETE FROM students "
            "WHERE email_verified = FALSE "
            "AND created_at < DATE_SUB(NOW(), INTERVAL 5 MINUTE)"
        )
    except Exception as e:
        print(f"[cleanup_unverified] {e}")


def _run_periodically(fn, interval_seconds, initial_delay=0):
    """Run fn in a daemon thread, then reschedule itself after interval_seconds."""
    def _wrapper():
        fn()
        t = threading.Timer(interval_seconds, _wrapper)
        t.daemon = True
        t.start()
    t = threading.Timer(initial_delay, _wrapper)
    t.daemon = True
    t.start()


def start_jobs():
    """Start background cleanup jobs. Call once at application startup."""
    _run_periodically(_cleanup_old_files,  interval_seconds=86400, initial_delay=120)  # every 24h, first run after 2min
    _run_periodically(_cleanup_unverified, interval_seconds=300,   initial_delay=60)   # every 5min, first run after 1min
