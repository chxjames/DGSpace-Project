-- Migration 009: Printers table
-- Allows admins to manage the list of available printers.
-- Created: 2026-03-18

USE DGSpace;

CREATE TABLE IF NOT EXISTS printers (
    printer_id   INT AUTO_INCREMENT PRIMARY KEY,
    printer_name VARCHAR(255) NOT NULL UNIQUE,
    model        VARCHAR(255),
    location     VARCHAR(255),
    status       ENUM('active', 'maintenance', 'retired') DEFAULT 'active',
    notes        TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
