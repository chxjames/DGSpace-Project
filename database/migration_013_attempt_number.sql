-- Migration 013: Add attempt_number to print_jobs
-- Tracks how many times a request has been attempted on a printer.
-- attempt_number=1 is the first try, 2 = first retry, 3 = second retry.
-- After 3 failed attempts the request is auto-sent back to the student.

ALTER TABLE print_jobs
  ADD COLUMN attempt_number TINYINT NOT NULL DEFAULT 1
    COMMENT '1=first attempt, 2=first retry, 3=second retry (max)';
