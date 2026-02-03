-- ============================================
-- ASSET MANAGEMENT SYSTEM - DATABASE SCHEMA
-- Run this in cPanel phpMyAdmin to create tables
-- ============================================

-- Create database (if not already created via cPanel)
-- CREATE DATABASE IF NOT EXISTS assetmgmt_db;
-- USE assetmgmt_db;

-- ============================================
-- ASSETS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS assets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    serial_number VARCHAR(100) UNIQUE NOT NULL,
    asset_type VARCHAR(50) NOT NULL DEFAULT 'Laptop',
    brand VARCHAR(50),
    model VARCHAR(100),
    specs TEXT,
    touch_screen BOOLEAN DEFAULT FALSE,
    processor VARCHAR(100),
    ram_gb INT,
    storage_type VARCHAR(20),
    storage_gb INT,
    os_installed VARCHAR(50),
    office_license_key VARCHAR(100),
    device_password VARCHAR(100),
    current_status VARCHAR(50) DEFAULT 'IN_STOCK_WORKING',
    current_location VARCHAR(200),
    purchase_date DATE,
    purchase_price DECIMAL(12,2),
    reuse_count INT DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_status (current_status),
    INDEX idx_brand (brand),
    INDEX idx_serial (serial_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- CLIENTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS clients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    client_name VARCHAR(200) NOT NULL,
    contact_person VARCHAR(100),
    email VARCHAR(100),
    phone VARCHAR(20),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    billing_rate DECIMAL(10,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_client_name (client_name),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- ASSIGNMENTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    asset_id INT NOT NULL,
    client_id INT,
    assignment_name VARCHAR(200),
    assignment_type VARCHAR(50) DEFAULT 'Rental',
    shipment_date DATE,
    return_date DATE,
    tracking_number VARCHAR(100),
    monthly_rate DECIMAL(10,2),
    status VARCHAR(50) DEFAULT 'ACTIVE',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_asset (asset_id),
    INDEX idx_client (client_id),
    INDEX idx_status (status),
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- ISSUES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS issues (
    id INT AUTO_INCREMENT PRIMARY KEY,
    asset_id INT,
    issue_title VARCHAR(200),
    issue_type VARCHAR(50),
    issue_category VARCHAR(100),
    description TEXT,
    reported_date DATE,
    resolved_date DATE,
    severity VARCHAR(20) DEFAULT 'Medium',
    status VARCHAR(50) DEFAULT 'Open',
    resolution_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_asset (asset_id),
    INDEX idx_status (status),
    INDEX idx_severity (severity),
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- REPAIRS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS repairs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    asset_id INT,
    repair_reference VARCHAR(100) UNIQUE,
    sent_date DATE,
    return_date DATE,
    expected_return DATE,
    vendor_name VARCHAR(200),
    repair_description TEXT,
    repair_cost DECIMAL(10,2),
    status VARCHAR(50) DEFAULT 'WITH_VENDOR',
    repair_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_asset (asset_id),
    INDEX idx_status (status),
    INDEX idx_reference (repair_reference),
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- STATE CHANGE LOG TABLE (Audit Trail)
-- ============================================
CREATE TABLE IF NOT EXISTS state_change_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    asset_id INT,
    serial_number VARCHAR(100),
    old_status VARCHAR(50),
    new_status VARCHAR(50),
    changed_by VARCHAR(50),
    user_role VARCHAR(20),
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_asset (asset_id),
    INDEX idx_serial (serial_number),
    INDEX idx_created (created_at),
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- USERS TABLE (for future authentication)
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'operations',
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- ACTIVITY LOG TABLE (Immutable Audit Trail)
-- ============================================
-- This table is APPEND-ONLY - no updates or deletes allowed
CREATE TABLE IF NOT EXISTS activity_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action_type VARCHAR(50) NOT NULL,          -- State Change, Assignment, Repair, Issue, Asset Created, etc.
    action_category VARCHAR(30) NOT NULL,      -- asset, client, assignment, billing, system
    asset_id INT,
    serial_number VARCHAR(100),
    client_id INT,
    client_name VARCHAR(200),
    old_value VARCHAR(100),                    -- Old status or value
    new_value VARCHAR(100),                    -- New status or value
    description TEXT,                          -- Human-readable description
    user_role VARCHAR(20) NOT NULL,
    user_identifier VARCHAR(100),              -- Username or session identifier
    ip_address VARCHAR(45),                    -- For future audit compliance
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    billing_impact BOOLEAN DEFAULT FALSE,      -- TRUE if action affects billing
    metadata JSON,                             -- Additional context (JSON)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_action_type (action_type),
    INDEX idx_action_category (action_category),
    INDEX idx_asset (asset_id),
    INDEX idx_serial (serial_number),
    INDEX idx_client (client_id),
    INDEX idx_user_role (user_role),
    INDEX idx_billing_impact (billing_impact),
    INDEX idx_created (created_at),
    INDEX idx_success (success),
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE SET NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- BILLING PERIODS TABLE (Month Close Tracking)
-- ============================================
-- Tracks the status of billing periods (OPEN/CLOSED)
-- Closed periods prevent retroactive modifications
CREATE TABLE IF NOT EXISTS billing_periods (
    id INT AUTO_INCREMENT PRIMARY KEY,
    period_year INT NOT NULL,
    period_month INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    closed_by VARCHAR(100),
    closed_at TIMESTAMP NULL,
    reopened_by VARCHAR(100),
    reopened_at TIMESTAMP NULL,
    total_revenue DECIMAL(12,2) DEFAULT 0,
    total_assets INT DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY idx_period (period_year, period_month),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- BILLING RECORDS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS billing_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    client_id INT NOT NULL,
    billing_month DATE NOT NULL,
    total_assets INT DEFAULT 0,
    total_amount DECIMAL(12,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'PENDING',
    invoice_number VARCHAR(50),
    paid_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_client (client_id),
    INDEX idx_month (billing_month),
    INDEX idx_status (status),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- VIEWS FOR COMMON QUERIES
-- ============================================

-- View: Assets with client info
CREATE OR REPLACE VIEW v_assets_with_clients AS
SELECT
    a.*,
    c.client_name,
    c.contact_person,
    c.email as client_email
FROM assets a
LEFT JOIN assignments asn ON a.id = asn.asset_id AND asn.status = 'ACTIVE'
LEFT JOIN clients c ON asn.client_id = c.id;

-- View: Asset status summary
CREATE OR REPLACE VIEW v_asset_status_summary AS
SELECT
    current_status,
    COUNT(*) as count,
    brand
FROM assets
GROUP BY current_status, brand;

-- View: Active assignments with details
CREATE OR REPLACE VIEW v_active_assignments AS
SELECT
    asn.*,
    a.serial_number,
    a.brand,
    a.model,
    a.asset_type,
    c.client_name
FROM assignments asn
JOIN assets a ON asn.asset_id = a.id
LEFT JOIN clients c ON asn.client_id = c.id
WHERE asn.status = 'ACTIVE';

-- ============================================
-- STORED PROCEDURE: Update Asset Status
-- ============================================
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS sp_update_asset_status(
    IN p_asset_id INT,
    IN p_new_status VARCHAR(50),
    IN p_new_location VARCHAR(200),
    IN p_user_role VARCHAR(20),
    OUT p_success BOOLEAN,
    OUT p_message VARCHAR(255)
)
BEGIN
    DECLARE v_current_status VARCHAR(50);
    DECLARE v_serial_number VARCHAR(100);
    DECLARE v_valid_transition BOOLEAN DEFAULT FALSE;

    -- Get current status
    SELECT current_status, serial_number
    INTO v_current_status, v_serial_number
    FROM assets WHERE id = p_asset_id;

    IF v_current_status IS NULL THEN
        SET p_success = FALSE;
        SET p_message = 'Asset not found';
    ELSE
        -- Validate transition (simplified - add full validation logic as needed)
        SET v_valid_transition = TRUE;

        IF v_valid_transition THEN
            -- Update asset
            UPDATE assets
            SET current_status = p_new_status,
                current_location = COALESCE(p_new_location, current_location)
            WHERE id = p_asset_id;

            -- Log the change
            INSERT INTO state_change_log
                (asset_id, serial_number, old_status, new_status, user_role, success)
            VALUES
                (p_asset_id, v_serial_number, v_current_status, p_new_status, p_user_role, TRUE);

            SET p_success = TRUE;
            SET p_message = 'Status updated successfully';
        ELSE
            -- Log failed attempt
            INSERT INTO state_change_log
                (asset_id, serial_number, old_status, new_status, user_role, success, error_message)
            VALUES
                (p_asset_id, v_serial_number, v_current_status, p_new_status, p_user_role, FALSE, 'Invalid transition');

            SET p_success = FALSE;
            SET p_message = CONCAT('Invalid transition from ', v_current_status, ' to ', p_new_status);
        END IF;
    END IF;
END //
DELIMITER ;
