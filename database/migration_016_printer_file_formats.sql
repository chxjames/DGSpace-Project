-- Migration 016: Add accepted_file_formats to printers table
-- Allows each printer to specify which slicer file formats it accepts (.ufp, .3mf, etc.)

USE DGSpace;

ALTER TABLE printers
    ADD COLUMN accepted_file_formats VARCHAR(64) NOT NULL DEFAULT 'ufp'
        COMMENT 'Comma-separated list of accepted slicer file formats, e.g. "ufp" or "3mf" or "ufp,3mf"'
        AFTER notes;
