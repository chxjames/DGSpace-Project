-- Migration 004: Add 'professor' and 'manager' to admins.role enum
-- Run: mysql -u root -p DGSpace < database/migration_004_add_professor_manager.sql

USE DGSpace;

-- MySQL does not allow direct ALTER to append enum values easily across versions.
-- The safe approach is to ALTER COLUMN with the full desired enum set.
ALTER TABLE admins
    MODIFY COLUMN role ENUM('super_admin', 'admin', 'moderator', 'professor', 'manager') DEFAULT 'admin';

-- Note: If your MySQL version or permissions prevent MODIFY, consider creating
-- a new temporary column, copying values, dropping the old column and renaming.
