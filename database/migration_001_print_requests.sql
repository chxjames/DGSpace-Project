-- ==========================================
-- Migration 001: 3D Print Requests Table
-- Created: 2026-02-05
-- ==========================================

USE DGSpace;

-- ==========================================
-- 3D Print Requests Table
-- ==========================================
CREATE TABLE IF NOT EXISTS print_requests (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    student_email VARCHAR(100) NOT NULL,
    project_name VARCHAR(200) NOT NULL,
    description TEXT,
    file_path VARCHAR(500),
    material_type ENUM('PLA', 'ABS', 'PETG', 'TPU', 'Nylon', 'Other') DEFAULT 'PLA',
    color_preference VARCHAR(50),
    estimated_weight_grams DECIMAL(10, 2),
    estimated_print_time_hours DECIMAL(10, 2),
    priority ENUM('low', 'normal', 'high', 'urgent') DEFAULT 'normal',
    status ENUM('pending', 'approved', 'rejected', 'in_progress', 'completed', 'cancelled') DEFAULT 'pending',
    admin_notes TEXT,
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    
    -- Foreign key constraint
    FOREIGN KEY (student_email) REFERENCES students(email) ON DELETE CASCADE,
    FOREIGN KEY (reviewed_by) REFERENCES admins(email) ON DELETE SET NULL,
    
    -- Indexes for better query performance
    INDEX idx_student_email (student_email),
    INDEX idx_status (status),
    INDEX idx_priority (priority),
    INDEX idx_created_at (created_at),
    INDEX idx_reviewed_by (reviewed_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ==========================================
-- Print Request Status History Table
-- Track all status changes for audit trail
-- ==========================================
CREATE TABLE IF NOT EXISTS print_request_history (
    history_id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NOT NULL,
    old_status ENUM('pending', 'approved', 'rejected', 'in_progress', 'completed', 'cancelled'),
    new_status ENUM('pending', 'approved', 'rejected', 'in_progress', 'completed', 'cancelled') NOT NULL,
    changed_by VARCHAR(100),
    change_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (request_id) REFERENCES print_requests(request_id) ON DELETE CASCADE,
    INDEX idx_request_id (request_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ==========================================
-- Sample Data (Optional - for testing)
-- ==========================================
-- Uncomment to insert sample data after creating students
-- INSERT INTO print_requests (student_email, project_name, description, material_type, status) 
-- VALUES ('test@sandiego.edu', 'Sample 3D Model', 'Test print request', 'PLA', 'pending');
