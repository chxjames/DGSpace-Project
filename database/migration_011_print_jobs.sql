-- Migration 011: Print Jobs (Scheduling Layer)
-- Adds the print_jobs table that links approved requests to specific printers
-- and tracks queue position, estimated timing, and execution status.
-- Also extends print_requests.status to include scheduling/execution stages.
-- Created: 2026-04-03

USE DGSpace;

-- ── Step 1: Extend print_requests status ENUM to include scheduling stages ──
ALTER TABLE print_requests
    MODIFY COLUMN status ENUM(
        'pending',
        'revision_requested',
        'approved',          -- approved + UFP ready, waiting to be scheduled
        'queued',            -- assigned to a printer, in its queue
        'printing',          -- currently being printed
        'completed',
        'failed',            -- print failed, may need requeue
        'rejected',
        'cancelled',
        'in_progress'        -- kept for legacy data
    ) NOT NULL DEFAULT 'pending';

-- ── Step 2: Create print_jobs table ──
CREATE TABLE IF NOT EXISTS print_jobs (
    job_id          INT AUTO_INCREMENT PRIMARY KEY,
    request_id      INT          NOT NULL,
    printer_id      INT          NOT NULL,
    queue_position  INT          NOT NULL DEFAULT 1 COMMENT 'Position in the printer queue (1 = next up)',
    status          ENUM(
        'queued',          -- in queue, not started yet
        'file_transferred',-- file copied to printer
        'printing',        -- currently printing
        'completed',       -- finished successfully
        'failed',          -- failed mid-print
        'cancelled'        -- removed from queue
    ) NOT NULL DEFAULT 'queued',
    assigned_by     VARCHAR(100) NOT NULL  COMMENT 'Admin/staff email who scheduled this job',
    assigned_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estimated_start DATETIME     NULL      COMMENT 'Estimated print start time',
    estimated_end   DATETIME     NULL      COMMENT 'Estimated print end time',
    started_at      TIMESTAMP    NULL,
    completed_at    TIMESTAMP    NULL,
    notes           TEXT         NULL      COMMENT 'Staff notes for this specific job run',

    FOREIGN KEY (request_id) REFERENCES print_requests(request_id) ON DELETE CASCADE,
    FOREIGN KEY (printer_id) REFERENCES printers(printer_id)       ON DELETE RESTRICT,

    INDEX idx_printer_queue  (printer_id, status, queue_position),
    INDEX idx_request_id     (request_id),
    INDEX idx_status         (status),
    INDEX idx_assigned_at    (assigned_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
