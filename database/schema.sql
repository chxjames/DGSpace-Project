-- ==========================================
-- DGSpace Database Schema
-- MySQL 8.0+
-- ==========================================

-- Create database
CREATE DATABASE IF NOT EXISTS DGSpace 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE DGSpace;

-- ==========================================
-- Students Table
-- ==========================================
CREATE TABLE IF NOT EXISTS students (
    email VARCHAR(100) PRIMARY KEY,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    department VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    INDEX idx_email_verified (email_verified)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ==========================================
-- Admins Table
-- ==========================================
CREATE TABLE IF NOT EXISTS admins (
    email VARCHAR(100) PRIMARY KEY,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    role ENUM('super_admin', 'admin', 'moderator') DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ==========================================
-- Email Verification Codes Table
-- ==========================================
CREATE TABLE IF NOT EXISTS email_verification_codes (
    email VARCHAR(100) NOT NULL,
    user_type ENUM('student', 'admin') NOT NULL,
    verification_code VARCHAR(6) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (email, user_type),
    INDEX idx_code (verification_code),
    INDEX idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ==========================================
-- Password Reset Tokens Table
-- ==========================================
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    email VARCHAR(100) NOT NULL,
    user_type ENUM('student', 'admin') NOT NULL,
    reset_token VARCHAR(64) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (email, user_type),
    INDEX idx_token (reset_token)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ==========================================
-- TOTP 2FA Secrets Table
-- ==========================================
CREATE TABLE IF NOT EXISTS totp_secrets (
    email VARCHAR(100) NOT NULL,
    user_type ENUM('student', 'admin') NOT NULL,
    secret VARCHAR(64) NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (email, user_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ==========================================
-- Notes
-- ==========================================
-- 1. Remember to create a dedicated database user:
--    CREATE USER 'dgspace_user'@'localhost' IDENTIFIED BY 'your_password';
--    GRANT ALL PRIVILEGES ON DGSpace.* TO 'dgspace_user'@'localhost';
--    FLUSH PRIVILEGES;
--
-- 2. Update backend/.env with your database credentials
-- 3. Passwords are hashed using bcrypt (never store plain text!)
-- 4. Email verification codes expire after 15 minutes
