-- Migration 014: Add print countdown tracking fields to print_jobs
-- print_end_expected: computed when job enters 'printing' = started_at + ufp_print_time_minutes
-- staff_notified:     flag to prevent duplicate "time's up" emails per job

ALTER TABLE print_jobs
  ADD COLUMN print_end_expected DATETIME NULL AFTER started_at,
  ADD COLUMN staff_notified TINYINT NOT NULL DEFAULT 0 AFTER print_end_expected;
