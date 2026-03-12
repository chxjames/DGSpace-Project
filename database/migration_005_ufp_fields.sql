-- Migration 005: Add UFP (Ultimaker Format Package) slicer data fields to print_requests
-- Applied: 2026-03-11
-- These fields are populated when an admin approves a request via the UFP upload flow.

ALTER TABLE print_requests
    ADD COLUMN ufp_file_path          VARCHAR(500)  DEFAULT NULL
        COMMENT 'Saved filename of the uploaded .ufp file in the uploads folder',
    ADD COLUMN ufp_original_name      VARCHAR(500)  DEFAULT NULL
        COMMENT 'Original .ufp filename as uploaded by the admin',
    ADD COLUMN ufp_print_time_minutes DECIMAL(10,2) DEFAULT NULL
        COMMENT 'Exact print time in minutes as calculated by Cura slicer',
    ADD COLUMN ufp_material_g         DECIMAL(10,2) DEFAULT NULL
        COMMENT 'Exact material weight in grams as calculated by Cura slicer';
