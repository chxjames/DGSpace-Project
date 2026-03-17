-- ==========================================
-- Migration 008: Student Staff Role
-- Adds a `role` column to the students table
-- so that admins can promote students to
-- 'student_staff'. Student staff can manage
-- print requests but cannot access reports.
-- ==========================================

USE DGSpace;

ALTER TABLE students
    ADD COLUMN role ENUM('student', 'student_staff') NOT NULL DEFAULT 'student'
    AFTER department;

CREATE INDEX idx_students_role ON students (role);
