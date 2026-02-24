-- Migration 003: Add 'revision_requested' to status enums
-- Run: mysql -u root -p DGSpace < database/migration_003_revision_requested.sql

USE DGSpace;

-- Add 'revision_requested' to print_requests.status enum
ALTER TABLE print_requests
    MODIFY COLUMN status ENUM('pending', 'approved', 'rejected', 'in_progress', 'completed', 'cancelled', 'revision_requested') DEFAULT 'pending';

-- Add 'revision_requested' to print_request_history.old_status and new_status enums
ALTER TABLE print_request_history
    MODIFY COLUMN old_status ENUM('pending', 'approved', 'rejected', 'in_progress', 'completed', 'cancelled', 'revision_requested');

ALTER TABLE print_request_history
    MODIFY COLUMN new_status ENUM('pending', 'approved', 'rejected', 'in_progress', 'completed', 'cancelled', 'revision_requested') NOT NULL;
