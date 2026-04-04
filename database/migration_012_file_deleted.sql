-- Migration 012: Add file_deleted flag to print_requests
-- Requests whose files have been purged by the 2-week cleanup job
-- will have file_deleted = 1 and will NOT appear in Ready to Schedule.

ALTER TABLE print_requests
  ADD COLUMN file_deleted TINYINT(1) NOT NULL DEFAULT 0
    COMMENT '1 = UFP file has been deleted by the cleanup job; request is archived';

-- Index for cleanup queries (find stale completed/failed/returned requests)
CREATE INDEX idx_pr_file_cleanup
  ON print_requests (status, file_deleted, updated_at);
