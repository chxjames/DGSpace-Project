-- ==========================================
-- Migration 006: Add deadline_date to print_requests
-- Created: 2026-03-11
-- ==========================================

USE DGSpace;

ALTER TABLE print_requests
    ADD COLUMN deadline_date DATE NULL COMMENT 'Optional project deadline set by student'
    AFTER slicer_material_g;

-- Index for quick sorting/filtering by deadline
ALTER TABLE print_requests
    ADD INDEX idx_deadline_date (deadline_date);
