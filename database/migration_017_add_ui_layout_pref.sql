-- migration_017_add_ui_layout_pref.sql
-- Adds ui_layout_preference column to students and admins tables.
-- Allowed values: 'dragdrop' (default) | 'dropdown'
-- Rollback: ALTER TABLE students DROP COLUMN ui_layout_preference;
--           ALTER TABLE admins   DROP COLUMN ui_layout_preference;

ALTER TABLE students
  ADD COLUMN ui_layout_preference VARCHAR(20) NOT NULL DEFAULT 'dragdrop';

ALTER TABLE admins
  ADD COLUMN ui_layout_preference VARCHAR(20) NOT NULL DEFAULT 'dragdrop';
