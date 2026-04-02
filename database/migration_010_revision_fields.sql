-- Migration 010: Add revision_fields column to print_requests
-- Stores a JSON array of field names that staff wants the student to update
-- e.g. '["stl", "description"]'  or '["material"]'
-- NULL means no specific restriction (student can edit everything)

ALTER TABLE print_requests
  ADD COLUMN revision_fields VARCHAR(255) DEFAULT NULL
  COMMENT 'JSON array of fields unlocked for student resubmit, set by staff on send-back';
