CREATE DATABASE IF NOT EXISTS security_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE security_demo;

CREATE TABLE IF NOT EXISTS activity_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    db_user VARCHAR(100) NOT NULL,
    user_role VARCHAR(30) NOT NULL DEFAULT 'Staff',
    client_host VARCHAR(100) NOT NULL DEFAULT 'localhost',
    operation VARCHAR(20) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    rows_affected INT NOT NULL DEFAULT 0,
    duration_ms FLOAT NOT NULL DEFAULT 0,
    queries_last_5m INT NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS',
    details VARCHAR(500) NOT NULL,
    -- NULL = not yet verified; 0 = confirmed normal; 1 = confirmed anomaly.
    ground_truth_anomaly TINYINT(1) NULL DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_event_time (event_time),
    INDEX idx_db_user (db_user),
    INDEX idx_operation (operation)
);

CREATE TABLE IF NOT EXISTS imported_general_log_keys (
    event_key CHAR(64) PRIMARY KEY,
    imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
