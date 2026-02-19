-- Migration 002: Add STL file upload support to print_requests
-- Run: mysql -u root -p DGSpace < database/migration_002_stl_upload.sql

USE DGSpace;

ALTER TABLE print_requests
    ADD COLUMN stl_file_path VARCHAR(255) NULL AFTER priority,
    ADD COLUMN stl_original_name VARCHAR(255) NULL AFTER stl_file_path;
