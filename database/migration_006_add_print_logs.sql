-- Migration 006: Add print_logs tables for Google Sheet import & weekly reports
-- Run this after migration_005 (or directly after migration_004 if 005 was reverted)
-- Created: 2026-03-05

-- ============================================================
-- Table: print_logs_raw
-- Stores the raw strings exactly as returned by gspread.
-- No conversion, no validation — a permanent audit trail.
-- ============================================================
CREATE TABLE IF NOT EXISTS print_logs_raw (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    batch_id            VARCHAR(36)     NOT NULL,           -- UUID per sync run
    row_index           INT             NOT NULL,           -- 1-based row number in Sheet
    student_email       VARCHAR(255),
    student_name        VARCHAR(255),
    operator_name       VARCHAR(255),
    printer_name        VARCHAR(255),
    print_time_raw      VARCHAR(50),                        -- exact gspread string, e.g. '8:13:00', ':26', '1 hour 13'
    material_used_raw   VARCHAR(50),                        -- exact gspread string from 'Print Consumables (g)'
    started_at_raw      VARCHAR(100),                       -- exact gspread string from 'Date Started'
    is_finished_raw     VARCHAR(50),                        -- exact gspread string from 'Finished?'
    actual_finish_raw   VARCHAR(100),                       -- exact gspread string from 'Actual Finish' (optional col)
    error_1_raw         VARCHAR(500),
    error_2_raw         VARCHAR(500),
    file_name_raw       VARCHAR(500),
    raw_json            JSON,                               -- full row stored as JSON for future-proofing
    imported_at         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Deduplicate by sheet row; re-sync overwrites same row
    UNIQUE KEY uq_raw_row (row_index)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- Table: print_logs_normalized
-- Parsed, typed values used directly by the weekly report.
-- Populated by report_service.import_from_sheet().
-- ============================================================
CREATE TABLE IF NOT EXISTS print_logs_normalized (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    raw_log_id              INT             NOT NULL,           -- FK to print_logs_raw
    batch_id                VARCHAR(36)     NOT NULL,
    row_index               INT             NOT NULL,

    -- Identity
    student_email           VARCHAR(255),
    student_name            VARCHAR(255),
    operator_name           VARCHAR(255),
    printer_name            VARCHAR(255),

    -- Timing (parsed)
    print_time_raw          VARCHAR(50),                        -- copy of raw for reference
    print_time_minutes      DECIMAL(10,2),                      -- NULL if parse fails
    slicer_time_minutes     DECIMAL(10,2),                      -- from print_requests (Cura, required)
    started_at              DATETIME,
    finished_at             DATETIME,                           -- derived: see priority comment below
    /*
        finished_at priority:
        1. actual_finish_raw parsed (staff hand-fill, highest authority)
        2. started_at + slicer_time_minutes
        3. started_at + print_time_minutes
        4. NULL
    */

    -- Material
    material_used_g         DECIMAL(10,2),                      -- NULL if parse fails
    slicer_material_g       DECIMAL(10,2),                      -- from print_requests (optional)

    -- Status
    is_finished             TINYINT(1),                         -- 1/0/NULL
    error_1                 VARCHAR(500),
    error_2                 VARCHAR(500),
    file_name               VARCHAR(500),

    -- Quality flags
    error_flag              TINYINT(1)      NOT NULL DEFAULT 0, -- 1 if any parse failure occurred
    error_reason            TEXT,                               -- comma-separated reasons

    -- Timestamps
    imported_at             TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_norm_row (row_index),
    CONSTRAINT fk_norm_raw FOREIGN KEY (raw_log_id) REFERENCES print_logs_raw(id) ON DELETE CASCADE,
    INDEX idx_printer      (printer_name),
    INDEX idx_operator     (operator_name),
    INDEX idx_started_at   (started_at),
    INDEX idx_student_email(student_email),
    INDEX idx_batch        (batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
