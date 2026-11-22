import os
import sys
from datetime import datetime
from typing import Tuple, Dict, Any
import pandas as pd
from dotenv import load_dotenv
import sqlalchemy
from sqlalchemy import text, create_engine

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

load_dotenv(os.path.join(BASE_DIR, ".env"))


def get_db_config() -> dict:
    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", 3306)),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DB", "fraud_analytics_db")
    }


def get_engine(include_db: bool = True) -> sqlalchemy.engine.Engine:
    cfg = get_db_config()
    db_part = f"/{cfg['database']}" if include_db else ""
    pwd_part = f":{cfg['password']}" if cfg['password'] else ""
    url = f"mysql+pymysql://{cfg['user']}{pwd_part}@{cfg['host']}:{cfg['port']}{db_part}?charset=utf8mb4"
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)


def ensure_database_exists():
    cfg = get_db_config()
    engine = get_engine(include_db=False)
    with engine.connect() as con:
        con.execute(text(f"CREATE DATABASE IF NOT EXISTS `{cfg['database']}` DEFAULT CHARACTER SET utf8mb4;"))
        con.commit()


def get_sql_path(filename: str) -> str:
    return os.path.join(BASE_DIR, "sql", filename)


def validate_raw_data(
    raw_txns_df: pd.DataFrame,
    users_df: pd.DataFrame = None,
    merchants_df: pd.DataFrame = None
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    total_incoming = len(raw_txns_df)
    df = raw_txns_df.copy()

    quarantine_mask = pd.Series(False, index=df.index)
    reasons = pd.Series("", index=df.index, dtype=str)

    # 1. Null check on required attributes
    null_txn = df["txn_id"].isna() | (df["txn_id"].astype(str).str.strip() == "")
    null_user = df["user_id"].isna() | (df["user_id"].astype(str).str.strip() == "")
    null_merchant = df["merchant_id"].isna() | (df["merchant_id"].astype(str).str.strip() == "")
    null_ts = df["timestamp"].isna() | (df["timestamp"].astype(str).str.strip() == "")

    null_mask = null_txn | null_user | null_merchant | null_ts
    if null_mask.any():
        quarantine_mask |= null_mask
        reasons[null_mask] = reasons[null_mask].apply(
            lambda r: (r + "; " if r else "") + "NULL_REQUIRED_FIELD: Missing essential attributes"
        )

    # 2. Amount must be positive numeric
    amt_numeric = pd.to_numeric(df["amount_inr"], errors="coerce")
    invalid_amt_mask = amt_numeric.isna() | (amt_numeric <= 0)
    if invalid_amt_mask.any():
        quarantine_mask |= invalid_amt_mask
        reasons[invalid_amt_mask] = reasons[invalid_amt_mask].apply(
            lambda r: (r + "; " if r else "") + "INVALID_AMOUNT: amount_inr <= 0 or non-numeric"
        )

    # 3. Duplicate transaction IDs
    dup_mask = df.duplicated(subset=["txn_id"], keep="first")
    if dup_mask.any():
        quarantine_mask |= dup_mask
        reasons[dup_mask] = reasons[dup_mask].apply(
            lambda r: (r + "; " if r else "") + "DUPLICATE_TXN_ID: Repeated transaction identifier"
        )

    # 4. Foreign key integrity checks
    if users_df is not None and "user_id" in users_df.columns:
        valid_user_ids = set(users_df["user_id"].dropna().unique())
        invalid_user_mask = ~df["user_id"].isin(valid_user_ids) & ~null_user
        if invalid_user_mask.any():
            quarantine_mask |= invalid_user_mask
            reasons[invalid_user_mask] = reasons[invalid_user_mask].apply(
                lambda r: (r + "; " if r else "") + "FK_VIOLATION: Unrecognized user_id"
            )

    if merchants_df is not None and "merchant_id" in merchants_df.columns:
        valid_merchant_ids = set(merchants_df["merchant_id"].dropna().unique())
        invalid_merchant_mask = ~df["merchant_id"].isin(valid_merchant_ids) & ~null_merchant
        if invalid_merchant_mask.any():
            quarantine_mask |= invalid_merchant_mask
            reasons[invalid_merchant_mask] = reasons[invalid_merchant_mask].apply(
                lambda r: (r + "; " if r else "") + "FK_VIOLATION: Unrecognized merchant_id"
            )

    clean_df = df[~quarantine_mask].copy()
    quarantine_df = df[quarantine_mask].copy()
    quarantine_df["quarantine_reason"] = reasons[quarantine_mask]
    quarantine_df["quarantined_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    clean_count = len(clean_df)
    quarantine_count = len(quarantine_df)
    dq_score = round((clean_count / total_incoming * 100.0), 2) if total_incoming > 0 else 0.0

    reason_counts = {}
    for r in quarantine_df["quarantine_reason"]:
        for part in r.split("; "):
            key = part.split(":")[0].strip()
            reason_counts[key] = reason_counts.get(key, 0) + 1

    metrics = {
        "total_incoming_rows": total_incoming,
        "clean_rows": clean_count,
        "quarantined_rows": quarantine_count,
        "dq_score_pct": dq_score,
        "reason_breakdown": reason_counts,
        "evaluation_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    return clean_df, quarantine_df, metrics


def generate_dim_date(min_date_str: str, max_date_str: str) -> pd.DataFrame:
    start_dt = pd.to_datetime(min_date_str).floor("D")
    end_dt = pd.to_datetime(max_date_str).ceil("D")
    date_range = pd.date_range(start=start_dt, end=end_dt, freq="D")
    
    dates = []
    for dt in date_range:
        dates.append({
            "date_id": int(dt.strftime("%Y%m%d")),
            "full_date": dt.date(),
            "year": int(dt.year),
            "quarter": int(dt.quarter),
            "month": int(dt.month),
            "month_name": dt.strftime("%B"),
            "day": int(dt.day),
            "day_of_week": int(dt.day_of_week + 1),
            "day_name": dt.strftime("%A"),
            "is_weekend": 1 if dt.day_of_week >= 5 else 0
        })
    return pd.DataFrame(dates)


def run_pipeline() -> dict:
    raw_dir = os.path.join(BASE_DIR, "data", "raw")
    users_file = os.path.join(raw_dir, "users.csv")
    merchants_file = os.path.join(raw_dir, "merchants.csv")
    txns_file = os.path.join(raw_dir, "transactions.csv")

    if not (os.path.exists(users_file) and os.path.exists(merchants_file) and os.path.exists(txns_file)):
        raise FileNotFoundError(
            f"Missing required raw CSV files in {raw_dir}. Run generate_data.py first."
        )

    ensure_database_exists()
    engine = get_engine(include_db=True)

    print("Reading raw CSV files from data/raw/...")
    users_df = pd.read_csv(users_file)
    merchants_df = pd.read_csv(merchants_file)
    raw_txns_df = pd.read_csv(txns_file)

    print("Running data validation...")
    clean_txns, quarantine_df, metrics = validate_raw_data(raw_txns_df, users_df, merchants_df)
    print(f"Validation summary: {metrics['clean_rows']} clean rows, {metrics['quarantined_rows']} quarantined (DQ Score: {metrics['dq_score_pct']}%)")

    clean_txns["timestamp_dt"] = pd.to_datetime(clean_txns["timestamp"])
    dim_date_df = generate_dim_date(
        str(clean_txns["timestamp_dt"].min()),
        str(clean_txns["timestamp_dt"].max())
    )

    clean_txns["date_id"] = clean_txns["timestamp_dt"].dt.strftime("%Y%m%d").astype(int)
    clean_txns["amount_inr"] = clean_txns["amount_inr"].astype(float)
    clean_txns["timestamp"] = clean_txns["timestamp_dt"].dt.strftime("%Y-%m-%d %H:%M:%S")

    fact_cols = [
        "txn_id", "user_id", "merchant_id", "date_id",
        "amount_inr", "timestamp", "payment_mode", "device_id", "city"
    ]
    fact_df = clean_txns[fact_cols].copy()

    print("Setting up Star Schema tables in MySQL...")
    with engine.connect() as con:
        con.execute(text("DROP VIEW IF EXISTS scored_transactions;"))
        con.execute(text("DROP TABLE IF EXISTS scored_transactions_table;"))
        con.execute(text("DROP TABLE IF EXISTS fact_transactions;"))
        con.execute(text("DROP TABLE IF EXISTS dim_users;"))
        con.execute(text("DROP TABLE IF EXISTS dim_merchants;"))
        con.execute(text("DROP TABLE IF EXISTS dim_date;"))
        con.execute(text("DROP TABLE IF EXISTS quarantine_logs;"))
        con.execute(text("DROP TABLE IF EXISTS etl_metrics;"))
        con.commit()

        schema_sql_path = get_sql_path("schema.sql")
        with open(schema_sql_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        for stmt in schema_sql.split(";"):
            clean_stmt = stmt.strip()
            if clean_stmt:
                con.execute(text(clean_stmt))
        con.commit()

    print("Loading data into dimensions and fact table...")
    users_df.to_sql("dim_users", engine, if_exists="append", index=False, chunksize=1000)
    merchants_df.to_sql("dim_merchants", engine, if_exists="append", index=False, chunksize=1000)
    dim_date_df.to_sql("dim_date", engine, if_exists="append", index=False, chunksize=1000)
    fact_df.to_sql("fact_transactions", engine, if_exists="append", index=False, chunksize=1000)

    if not quarantine_df.empty:
        quar_cols = [
            "txn_id", "user_id", "merchant_id", "amount_inr",
            "timestamp", "payment_mode", "device_id", "city",
            "quarantine_reason", "quarantined_at"
        ]
        for col in quar_cols:
            if col not in quarantine_df.columns:
                quarantine_df[col] = None
        quarantine_df[quar_cols].to_sql("quarantine_logs", engine, if_exists="append", index=False, chunksize=1000)

    metrics_df = pd.DataFrame([{
        "total_incoming_rows": metrics["total_incoming_rows"],
        "clean_rows_loaded": metrics["clean_rows"],
        "quarantined_rows": metrics["quarantined_rows"],
        "dq_score_pct": metrics["dq_score_pct"],
        "run_timestamp": metrics["evaluation_timestamp"]
    }])
    metrics_df.to_sql("etl_metrics", engine, if_exists="append", index=False)

    print("Compiling fraud scoring view and materializing table...")
    with engine.connect() as con:
        fraud_rules_path = get_sql_path("fraud_rules.sql")
        with open(fraud_rules_path, "r", encoding="utf-8") as f:
            fraud_rules_sql = f.read()

        for stmt in fraud_rules_sql.split(";"):
            clean_stmt = stmt.strip()
            if clean_stmt:
                con.execute(text(clean_stmt))
        con.commit()

        # Materialize scored table to keep dashboard queries fast
        con.execute(text("DROP TABLE IF EXISTS scored_transactions_table;"))
        con.execute(text("""
            CREATE TABLE scored_transactions_table AS 
            SELECT * FROM scored_transactions;
        """))
        con.execute(text("ALTER TABLE scored_transactions_table ADD INDEX idx_sc_risk (risk_score);"))
        con.execute(text("ALTER TABLE scored_transactions_table ADD INDEX idx_sc_band (risk_band);"))
        con.execute(text("ALTER TABLE scored_transactions_table ADD INDEX idx_sc_ts (timestamp);"))
        con.execute(text("ALTER TABLE scored_transactions_table ADD INDEX idx_sc_user (user_id);"))
        con.commit()

        distribution = con.execute(text("""
            SELECT risk_band, COUNT(*) AS cnt, ROUND(SUM(amount_inr), 2) AS total_val
            FROM scored_transactions_table
            GROUP BY risk_band
            ORDER BY cnt DESC;
        """)).fetchall()

        print("ETL completed successfully. Risk band distribution:")
        for band, count, val in distribution:
            print(f"  {band:15s}: {count:6d} txns | Rs {val:,.2f}")

    return metrics


if __name__ == "__main__":
    run_pipeline()
