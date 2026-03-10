-- Migration 007: Add Cura slicer estimate fields to print_requests
-- Run after migration_006
-- Created: 2026-03-05

ALTER TABLE print_requests
    ADD COLUMN slicer_time_minutes  DECIMAL(10,2) NULL        COMMENT 'Cura estimated print time (minutes), required on new requests',
    ADD COLUMN slicer_material_g    DECIMAL(10,2) NULL        COMMENT 'Cura estimated material usage (grams), optional';

-- NOTE: Column is added as NULL initially so existing rows are not broken.
-- Application layer enforces NOT NULL for new submissions (returns HTTP 400 if missing).
-- If you want to enforce at DB level for new rows only, you can run a follow-up:
--   UPDATE print_requests SET slicer_time_minutes = 0 WHERE slicer_time_minutes IS NULL;
--   ALTER TABLE print_requests MODIFY slicer_time_minutes DECIMAL(10,2) NOT NULL DEFAULT 0;
