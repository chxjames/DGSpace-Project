-- ==========================================
-- Migration 004: Senior Design & Project Context Fields
-- Created: 2026-03-10
-- ==========================================

USE DGSpace;

ALTER TABLE print_requests
    ADD COLUMN is_senior_design  BOOLEAN NOT NULL DEFAULT FALSE
        COMMENT 'Is this a Senior Design project?'
        AFTER color_preference,
    ADD COLUMN project_context   ENUM('class', 'individual') NOT NULL DEFAULT 'individual'
        COMMENT 'Is this for a class or an individual project?'
        AFTER is_senior_design;
