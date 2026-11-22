-- Star Schema DDL for MySQL (fraud_analytics_db)

CREATE DATABASE IF NOT EXISTS fraud_analytics_db;
USE fraud_analytics_db;

-- User dimension
CREATE TABLE IF NOT EXISTS dim_users (
    user_id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    city VARCHAR(50),
    account_age_days INT,
    kyc_tier VARCHAR(50),
    avg_monthly_spend_inr DECIMAL(12, 2),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Merchant dimension
CREATE TABLE IF NOT EXISTS dim_merchants (
    merchant_id VARCHAR(32) PRIMARY KEY,
    merchant_name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    risk_tier VARCHAR(20) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Calendar dimension
CREATE TABLE IF NOT EXISTS dim_date (
    date_id INT PRIMARY KEY,
    full_date DATE NOT NULL,
    year INT NOT NULL,
    quarter INT NOT NULL,
    month INT NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    day INT NOT NULL,
    day_of_week INT NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    is_weekend TINYINT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Clean validated transactions
CREATE TABLE IF NOT EXISTS fact_transactions (
    txn_id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32) NOT NULL,
    merchant_id VARCHAR(32) NOT NULL,
    date_id INT NOT NULL,
    amount_inr DECIMAL(12, 2) NOT NULL,
    timestamp DATETIME NOT NULL,
    payment_mode VARCHAR(30) NOT NULL,
    device_id VARCHAR(50),
    city VARCHAR(50),
    CONSTRAINT fk_fact_users FOREIGN KEY (user_id) REFERENCES dim_users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_fact_merchants FOREIGN KEY (merchant_id) REFERENCES dim_merchants(merchant_id) ON DELETE CASCADE,
    CONSTRAINT fk_fact_date FOREIGN KEY (date_id) REFERENCES dim_date(date_id) ON DELETE CASCADE,
    INDEX idx_fact_user (user_id),
    INDEX idx_fact_ts (timestamp),
    INDEX idx_fact_date (date_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Isolated invalid rows (nulls, duplicates, negative amounts)
CREATE TABLE IF NOT EXISTS quarantine_logs (
    quarantine_id INT AUTO_INCREMENT PRIMARY KEY,
    txn_id VARCHAR(32),
    user_id VARCHAR(32),
    merchant_id VARCHAR(32),
    amount_inr DECIMAL(12, 2),
    timestamp VARCHAR(50),
    payment_mode VARCHAR(30),
    device_id VARCHAR(50),
    city VARCHAR(50),
    quarantine_reason VARCHAR(255) NOT NULL,
    quarantined_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Ingestion metrics
CREATE TABLE IF NOT EXISTS etl_metrics (
    run_id INT AUTO_INCREMENT PRIMARY KEY,
    total_incoming_rows INT NOT NULL,
    clean_rows_loaded INT NOT NULL,
    quarantined_rows INT NOT NULL,
    dq_score_pct DECIMAL(5, 2) NOT NULL,
    run_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
