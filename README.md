# Fintech Fraud Analytics and Risk Scoring Engine

## Project Overview & Problem Statement
I built this project to practice writing analytical MySQL 8.0 window functions, designing a Kimball-style Star Schema, and implementing automated data quality validation for digital payment workflows. The dataset models Indian fintech transaction patterns (UPI and cards), where fraud signals typically manifest as high-velocity bursts, late-night spending spikes, or rapid fund transfers into high-risk merchant categories.

## Tech Stack
- **Database:** MySQL Community Server 8.0 / 8.4 (Window Functions, CTEs, B-Tree Indexes)
- **Programming Language:** Python 3.10+ (tested on Python 3.12)
- **Database Connectivity:** SQLAlchemy & PyMySQL
- **Web Dashboard:** Streamlit
- **Visualization:** Plotly
- **Testing:** Pytest

## Architecture and Schema

### Data Flow
```text
Raw CSV Files (users, merchants, transactions)
                    │
                    ▼
       Python Data Validation (src/etl.py)
        ├── Invalid rows (1%) ──► quarantine_logs table
        └── Clean rows (99%)  ──► MySQL Star Schema
                                    ├── dim_users
                                    ├── dim_merchants
                                    ├── dim_date
                                    └── fact_transactions
                                            │
                                            ▼
                           SQL Fraud Scoring Engine (sql/fraud_rules.sql)
                           (MySQL 8.0 CTEs + Window Functions)
                                            │
                                            ▼
                           scored_transactions_table / View
                                            │
                                            ▼
                              Streamlit Dashboard (app.py)
```

### Star Schema Tables
- **dim_users:** User profile metadata (`user_id`, `name`, `city`, `kyc_tier`, `avg_monthly_spend_inr`).
- **dim_merchants:** Merchant categories and risk tiers (`merchant_id`, `merchant_name`, `category`, `risk_tier`).
- **dim_date:** Calendar dimension extracted from transaction timestamps.
- **fact_transactions:** Clean transactions linked to dimension tables with foreign keys and B-tree indexes on `user_id` and `timestamp`.
- **quarantine_logs:** Audit table capturing defective rows (null merchant IDs, duplicate transaction IDs, non-positive amounts) and rejection reasons.
- **etl_metrics:** Pipeline audit log recording total rows processed, clean records loaded, quarantined count, and final Data Quality Score.

## Fraud Scoring Logic
The scoring engine runs in MySQL 8.0 using Common Table Expressions and window functions. Each transaction is scored from 0 to 100 based on four cumulative rules:

| Rule | Weight | SQL Logic / Condition | Rationale |
| :--- | :--- | :--- | :--- |
| **Rule 1: High-Value Spike** | +40 pts | `amount_inr > 3 * AVG(amount_inr) OVER (PARTITION BY user_id)` | Detects sudden spending anomalies compared to the user's historical baseline. |
| **Rule 2: Velocity Burst** | +35 pts | `COUNT(*) OVER (PARTITION BY user_id ORDER BY timestamp RANGE BETWEEN INTERVAL 5 MINUTE PRECEDING AND CURRENT ROW) >= 4` | Detects rapid-fire bot or card-testing activity (4 or more transactions within 5 minutes). |
| **Rule 3: Late-Night Anomaly** | +15 pts | `HOUR(timestamp) BETWEEN 1 AND 3 AND amount_inr > 10000` | Flags high-value transfers initiated during off-hours (1:00 AM to 3:59 AM). |
| **Rule 4: High-Risk Merchant** | +10 pts | `m.risk_tier = 'HIGH'` | Adds weight when funds flow to elevated-risk merchants (crypto, gaming, p2p). |

Final risk score calculation:
```sql
risk_score = LEAST(100, rule_1_pts + rule_2_pts + rule_3_pts + rule_4_pts)
```

Risk bands:
- **HIGH:** Score >= 70
- **MEDIUM:** Score 40 to 69
- **LOW:** Score < 40

## Local Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/badal6362/fintech-fraud-analytics-mysql.git
cd fintech-fraud-analytics-mysql
```

### 2. Configure Environment
Copy `.env.example` to `.env` and enter your local MySQL credentials:
```bash
cp .env.example .env
```
Update `.env` with your database credentials:
```ini
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DB=fraud_analytics_db
```

### 3. Create Virtual Environment and Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Generate Synthetic Data
Generates 10,000 transactions across 1,000 users and 39 merchants in `data/raw/`, injecting realistic fraud spikes and ~1% defective rows for quality testing:
```bash
python src/generate_data.py
```

### 5. Run Validation, Star Schema ETL, and SQL Scoring
Creates the database if missing, executes `sql/schema.sql`, quarantines invalid records, loads clean data into the Star Schema, and materializes `scored_transactions_table`:
```bash
python src/etl.py
```

### 6. Run the Test Suite
```bash
pytest tests/test_engine.py -v
```

### 7. Launch the Streamlit Dashboard
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser. The dashboard includes:
- **Overview:** KPI cards, daily flagged volume, and risk band breakdowns.
- **Flagged Transactions:** Filterable triage queue with single-transaction detail views and a 10-transaction user historical audit trail.
- **Data Quality & SQL:** Ingestion audit logs, quarantined rows table, and an interactive MySQL query runner.

## Limitations and Next Steps
1. **Synthetic Data:** The dataset is generated synthetically to mirror Indian UPI transaction frequencies. While it models realistic fraud patterns, real production workloads contain broader variations in user behavior and merchant networks.
2. **Rule-Based Heuristics vs. ML:** The scoring engine currently relies on fixed SQL window heuristics. A logical next step is training a supervised classification model (e.g., XGBoost or LightGBM) to learn dynamic risk weights and combining it with SQL rule thresholds.
3. **Batch ETL vs. Streaming:** Data ingestion and scoring currently run as a batch ETL job. In a live payment gateway, the velocity rule would be evaluated in real time using a streaming engine like Apache Flink or Kafka Streams with Redis caching for user baselines.
