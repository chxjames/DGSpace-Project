-- Migration 015: Drop FK constraint on print_requests.student_email
-- Allows admins (and future non-student users) to submit print requests.
-- The student_email column is kept; referential integrity is enforced at the
-- application layer instead of the database layer.
--
-- Created: 2026-04-13

USE DGSpace;

-- Step 1: Find and drop the FK constraint on student_email.
-- MySQL requires knowing the exact constraint name, so we use a stored procedure
-- that looks it up from information_schema and drops it dynamically.

DROP PROCEDURE IF EXISTS drop_student_email_fk;

DELIMITER $$
CREATE PROCEDURE drop_student_email_fk()
BEGIN
    DECLARE _constraint VARCHAR(200);

    SELECT CONSTRAINT_NAME
    INTO   _constraint
    FROM   information_schema.KEY_COLUMN_USAGE
    WHERE  TABLE_SCHEMA    = DATABASE()
      AND  TABLE_NAME      = 'print_requests'
      AND  COLUMN_NAME     = 'student_email'
      AND  REFERENCED_TABLE_NAME IS NOT NULL
    LIMIT 1;

    IF _constraint IS NOT NULL THEN
        SET @sql = CONCAT('ALTER TABLE print_requests DROP FOREIGN KEY `', _constraint, '`');
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
        SELECT CONCAT('Dropped FK: ', _constraint) AS result;
    ELSE
        SELECT 'No FK found on student_email — already dropped or never existed.' AS result;
    END IF;
END$$
DELIMITER ;

CALL drop_student_email_fk();
DROP PROCEDURE IF EXISTS drop_student_email_fk;
