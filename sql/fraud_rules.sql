-- MySQL 8.0+ Fraud Scoring View using CTEs and Window Functions

USE fraud_analytics_db;

DROP VIEW IF EXISTS scored_transactions;

CREATE VIEW scored_transactions AS
WITH transaction_windows AS (
    SELECT 
        f.txn_id,
        f.user_id,
        u.name AS user_name,
        u.city AS user_city,
        u.kyc_tier,
        u.avg_monthly_spend_inr,
        f.merchant_id,
        m.merchant_name,
        m.category AS merchant_category,
        m.risk_tier AS merchant_risk_tier,
        f.date_id,
        f.amount_inr,
        f.timestamp,
        f.payment_mode,
        f.device_id,
        f.city AS txn_city,
        
        -- Historical average per user to catch sudden spikes
        AVG(f.amount_inr) OVER (PARTITION BY f.user_id) AS user_avg_amount,
        
        -- Rolling 5-minute velocity window to catch rapid carding attempts
        COUNT(*) OVER (
            PARTITION BY f.user_id 
            ORDER BY f.timestamp 
            RANGE BETWEEN INTERVAL 5 MINUTE PRECEDING AND CURRENT ROW
        ) AS txns_last_5min,
        
        HOUR(f.timestamp) AS txn_hour
    FROM fact_transactions f
    INNER JOIN dim_users u ON f.user_id = u.user_id
    INNER JOIN dim_merchants m ON f.merchant_id = m.merchant_id
),

rule_evaluations AS (
    SELECT
        *,
        -- Rule 1: Amount spike (>3x the user's average)
        CASE 
            WHEN amount_inr > (3.0 * user_avg_amount) THEN 40 
            ELSE 0 
        END AS rule_1_score,
        
        -- Rule 2: 4 or more transactions by the same user within 5 minutes
        CASE 
            WHEN txns_last_5min >= 4 THEN 35 
            ELSE 0 
        END AS rule_2_score,
        
        -- Rule 3: Late night transactions (1 AM to 4 AM) above Rs 10,000
        CASE 
            WHEN txn_hour BETWEEN 1 AND 3 AND amount_inr > 10000.0 THEN 15 
            ELSE 0 
        END AS rule_3_score,
        
        -- Rule 4: High risk merchant category (crypto, gambling, luxury jewelry)
        CASE 
            WHEN merchant_risk_tier = 'High' THEN 10 
            ELSE 0 
        END AS rule_4_score
    FROM transaction_windows
),

scored_base AS (
    SELECT
        *,
        (rule_1_score + rule_2_score + rule_3_score + rule_4_score) AS raw_risk_score,
        LEAST(100, rule_1_score + rule_2_score + rule_3_score + rule_4_score) AS risk_score,
        CONCAT_WS(', ',
            CASE WHEN rule_1_score > 0 THEN 'RULE_1: Amount Spike (>3x Avg)' ELSE NULL END,
            CASE WHEN rule_2_score > 0 THEN 'RULE_2: Velocity Burst (>=4 txns in 5 min)' ELSE NULL END,
            CASE WHEN rule_3_score > 0 THEN 'RULE_3: Late-Night High Value (1-4 AM > Rs 10k)' ELSE NULL END,
            CASE WHEN rule_4_score > 0 THEN 'RULE_4: High-Risk Merchant Category' ELSE NULL END
        ) AS rule_reasons
    FROM rule_evaluations
)

SELECT
    txn_id,
    user_id,
    user_name,
    user_city,
    kyc_tier,
    avg_monthly_spend_inr,
    merchant_id,
    merchant_name,
    merchant_category,
    merchant_risk_tier,
    date_id,
    amount_inr,
    timestamp,
    txn_hour,
    payment_mode,
    device_id,
    txn_city,
    ROUND(user_avg_amount, 2) AS user_avg_amount,
    txns_last_5min,
    rule_1_score,
    rule_2_score,
    rule_3_score,
    rule_4_score,
    risk_score,
    CASE 
        WHEN risk_score >= 70 THEN 'High Risk'
        WHEN risk_score >= 40 THEN 'Medium Review'
        ELSE 'Safe'
    END AS risk_band,
    CASE 
        WHEN rule_reasons IS NULL OR rule_reasons = '' THEN 'CLEAN: Normal Activity'
        ELSE rule_reasons
    END AS reason_code
FROM scored_base;
