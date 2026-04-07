-- Migration 010: Expand totp_secrets.user_type ENUM to include student_staff
-- Fixes: student_staff users could not set up 2FA (INSERT rejected by MySQL ENUM constraint)

ALTER TABLE totp_secrets
  MODIFY COLUMN user_type ENUM('student', 'admin', 'student_staff') NOT NULL;
