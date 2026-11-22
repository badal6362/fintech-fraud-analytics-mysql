"""
Test Suite for Fintech Fraud Analytics & Risk Scoring Engine (MySQL 8.0+)
Verifies Data Generation, Quarantine & Validation, MySQL Star Schema ETL,
MySQL Window Functions Fraud Rules, and Live Database Integrity.
"""

import os
import sys
import pytest
import pandas as pd
from sqlalchemy import text

# Bootstrap root path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src import generate_data, etl


def test_data_generation_files_exist():
    """Verify raw CSV files exist and have required row counts and schemas."""
    raw_dir = os.path.join(BASE_DIR, "data", "raw")
    users_path = os.path.join(raw_dir, "users.csv")
    merchants_path = os.path.join(raw_dir, "merchants.csv")
    txns_path = os.path.join(raw_dir, "transactions.csv")

    assert os.path.exists(users_path), "users.csv missing"
    assert os.path.exists(merchants_path), "merchants.csv missing"
    assert os.path.exists(txns_path), "transactions.csv missing"

    df_u = pd.read_csv(users_path)
    df_m = pd.read_csv(merchants_path)
    df_t = pd.read_csv(txns_path)

    assert len(df_u) == 1000, f"Expected 1000 users, got {len(df_u)}"
    assert len(df_m) >= 30, f"Expected >=30 merchants, got {len(df_m)}"
    assert len(df_t) == 10000, f"Expected 10000 transactions, got {len(df_t)}"

    assert set(["user_id", "name", "city", "account_age_days", "kyc_tier", "avg_monthly_spend_inr"]).issubset(df_u.columns)
    assert set(["merchant_id", "merchant_name", "category", "risk_tier"]).issubset(df_m.columns)
    assert set(["txn_id", "user_id", "merchant_id", "amount_inr", "timestamp", "payment_mode", "device_id", "city"]).issubset(df_t.columns)


def test_data_validation_and_quarantine():
    """Verify messy data is quarantined and Data Quality Score is calculated."""
    raw_dir = os.path.join(BASE_DIR, "data", "raw")
    df_t = pd.read_csv(os.path.join(raw_dir, "transactions.csv"))
    df_u = pd.read_csv(os.path.join(raw_dir, "users.csv"))
    df_m = pd.read_csv(os.path.join(raw_dir, "merchants.csv"))

    clean_df, quarantine_df, metrics = etl.validate_raw_data(df_t, df_u, df_m)

    assert metrics["quarantined_rows"] == 100, f"Expected 100 quarantined rows, got {metrics['quarantined_rows']}"
    assert metrics["clean_rows"] == 9900, f"Expected 9900 clean rows, got {metrics['clean_rows']}"
    assert metrics["dq_score_pct"] == 99.0, f"Expected 99.0% DQ score, got {metrics['dq_score_pct']}"

    reasons = metrics["reason_breakdown"]
    assert "NULL_REQUIRED_FIELD" in reasons, "Missing NULL quarantine reason"
    assert "DUPLICATE_TXN_ID" in reasons, "Missing DUPLICATE quarantine reason"
    assert "INVALID_AMOUNT" in reasons, "Missing INVALID_AMOUNT quarantine reason"


def test_star_schema_tables_in_mysql():
    """Verify MySQL warehouse tables, row counts, and dimensional modeling."""
    engine = etl.get_engine(include_db=True)
    with engine.connect() as con:
        tables_df = pd.read_sql_query(text("SHOW TABLES;"), con)
        tables = tables_df.iloc[:, 0].tolist()

        expected_tables = [
            "dim_users", "dim_merchants", "dim_date",
            "fact_transactions", "quarantine_logs", "etl_metrics",
            "scored_transactions_table"
        ]
        for tbl in expected_tables:
            assert tbl in tables, f"Expected table '{tbl}' in MySQL database"

        fact_cnt = con.execute(text("SELECT COUNT(*) FROM fact_transactions;")).fetchone()[0]
        users_cnt = con.execute(text("SELECT COUNT(*) FROM dim_users;")).fetchone()[0]
        merch_cnt = con.execute(text("SELECT COUNT(*) FROM dim_merchants;")).fetchone()[0]
        date_cnt = con.execute(text("SELECT COUNT(*) FROM dim_date;")).fetchone()[0]
        quar_cnt = con.execute(text("SELECT COUNT(*) FROM quarantine_logs;")).fetchone()[0]

        assert fact_cnt == 9900, f"Expected 9900 fact rows, got {fact_cnt}"
        assert users_cnt == 1000, f"Expected 1000 dim_users rows, got {users_cnt}"
        assert merch_cnt >= 30, f"Expected >=30 dim_merchants rows, got {merch_cnt}"
        assert date_cnt >= 60, f"Expected >=60 dim_date rows, got {date_cnt}"
        assert quar_cnt == 100, f"Expected 100 quarantine rows, got {quar_cnt}"


def test_mysql_fraud_scoring_engine():
    """Verify MySQL CTEs & window functions and risk score outputs."""
    engine = etl.get_engine(include_db=True)
    with engine.connect() as con:
        df_scored = pd.read_sql_query(text("""
            SELECT 
                risk_score,
                risk_band,
                rule_1_score,
                rule_2_score,
                rule_3_score,
                rule_4_score,
                reason_code
            FROM scored_transactions_table;
        """), con)

    assert df_scored["risk_score"].min() >= 0, "Risk score must be >= 0"
    assert df_scored["risk_score"].max() <= 100, "Risk score must be capped at 100"

    valid_bands = set(["High Risk", "Medium Review", "Safe"])
    actual_bands = set(df_scored["risk_band"].unique())
    assert actual_bands.issubset(valid_bands), f"Invalid risk bands: {actual_bands - valid_bands}"

    high_risk_min = df_scored[df_scored["risk_band"] == "High Risk"]["risk_score"].min()
    assert high_risk_min >= 70, f"High Risk score minimum should be >= 70, got {high_risk_min}"

    med_risk = df_scored[df_scored["risk_band"] == "Medium Review"]["risk_score"]
    assert med_risk.min() >= 40 and med_risk.max() <= 69, "Medium Review scores must be between 40 and 69"

    safe_max = df_scored[df_scored["risk_band"] == "Safe"]["risk_score"].max()
    assert safe_max < 40, f"Safe scores must be < 40, got {safe_max}"

    high_risk_sample = df_scored[df_scored["risk_band"] == "High Risk"].iloc[0]
    assert "RULE_" in high_risk_sample["reason_code"], "Reason code must reference triggered rules"

    assert set(df_scored["rule_1_score"].unique()).issubset({0, 40})
    assert set(df_scored["rule_2_score"].unique()).issubset({0, 35})
    assert set(df_scored["rule_3_score"].unique()).issubset({0, 15})
    assert set(df_scored["rule_4_score"].unique()).issubset({0, 10})


def test_dashboard_filtering_and_aggregations():
    """Verify that all queries and aggregations powering the Streamlit tabs execute cleanly."""
    import app
    df_scored, df_quarantine, df_dq = app.load_warehouse_data()

    assert df_scored is not None and not df_scored.empty, "Scored data must load from MySQL"
    assert df_quarantine is not None and len(df_quarantine) == 100, "Quarantine logs must load 100 rows"
    assert df_dq is not None and not df_dq.empty, "ETL metrics must load"

    total_volume = df_scored["amount_inr"].sum()
    high_risk_txns = df_scored[df_scored["risk_band"] == "High Risk"]
    flagged_fraud_rate = len(high_risk_txns) / len(df_scored) * 100.0
    amount_at_risk = high_risk_txns["amount_inr"].sum()

    assert total_volume > 5_000_000, "Total volume should exceed ₹50 L"
    assert flagged_fraud_rate > 0.0, "Fraud rate should be positive"
    assert amount_at_risk > 100_000, "Amount at risk should exceed ₹1 L"

    triage_candidates = df_scored[df_scored["risk_band"] == "High Risk"].sort_values(
        by=["risk_score", "amount_inr"], ascending=[False, False]
    )
    assert not triage_candidates.empty, "Triage queue must have candidates"

    # Test user transaction history lookup (last 10 transactions from MySQL)
    sample_user = triage_candidates.iloc[0]["user_id"]
    engine = etl.get_engine(include_db=True)
    with engine.connect() as con:
        user_history = pd.read_sql_query(text(f"""
            SELECT txn_id, timestamp, amount_inr, risk_score, reason_code
            FROM scored_transactions_table
            WHERE user_id = '{sample_user}'
            ORDER BY timestamp DESC
            LIMIT 10;
        """), con)

    assert not user_history.empty, f"User {sample_user} must have history in MySQL"
    assert len(user_history) <= 10, "History should be at most 10 transactions"
