import os
import sys
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src import etl, generate_data

# Page setup
st.set_page_config(
    page_title="Fraud Risk Analytics Engine",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clean, neutral theme styling without neon gradients
st.markdown("""
<style>
    /* Metric Cards */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 14px 18px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    div[data-testid="stMetric"] label {
        color: #64748b !important;
        font-weight: 500;
        font-size: 0.85rem;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #0f172a !important;
        font-weight: 700;
        font-size: 1.6rem;
    }
    
    /* Risk Badges */
    .badge-high {
        background-color: #fee2e2;
        color: #b91c1c;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 600;
        border: 1px solid #fca5a5;
    }
    .badge-med {
        background-color: #fef3c7;
        color: #b45309;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 600;
        border: 1px solid #fde68a;
    }
    .badge-safe {
        background-color: #d1fae5;
        color: #047857;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 600;
        border: 1px solid #a7f3d0;
    }

    .detail-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)


def format_inr(amount: float) -> str:
    if amount is None or pd.isna(amount):
        return "Rs 0.00"
    abs_amt = abs(amount)
    sign = "-" if amount < 0 else ""
    if abs_amt >= 10_000_000:
        return f"{sign}Rs {abs_amt / 10_000_000:.2f} Cr"
    elif abs_amt >= 100_000:
        return f"{sign}Rs {abs_amt / 100_000:.2f} L"
    else:
        return f"{sign}Rs {abs_amt:,.2f}"


def load_warehouse_data():
    try:
        engine = etl.get_engine(include_db=True)
        with engine.connect() as con:
            df_scored = pd.read_sql_query(
                text("SELECT * FROM scored_transactions_table ORDER BY timestamp ASC;"), con
            )
            df_quarantine = pd.read_sql_query(
                text("SELECT * FROM quarantine_logs ORDER BY quarantine_id ASC;"), con
            )
            df_dq = pd.read_sql_query(
                text("SELECT * FROM etl_metrics ORDER BY run_id DESC LIMIT 1;"), con
            )
        if not df_scored.empty:
            df_scored["timestamp"] = pd.to_datetime(df_scored["timestamp"])
            df_scored["amount_inr"] = df_scored["amount_inr"].astype(float)
        return df_scored, df_quarantine, df_dq
    except Exception:
        return None, None, None


# Sidebar
st.sidebar.title("Fraud Risk Engine")
cfg = etl.get_db_config()
st.sidebar.caption(f"MySQL: {cfg['database']} on {cfg['host']}:{cfg['port']}")

if st.sidebar.button("Run ETL Pipeline", use_container_width=True, type="primary"):
    with st.spinner("Running validation and re-scoring in MySQL..."):
        try:
            metrics = etl.run_pipeline()
            st.sidebar.success(f"ETL completed. Data Quality Score: {metrics['dq_score_pct']}%")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"ETL failed: {e}")

df_scored, df_quarantine, df_dq = load_warehouse_data()

if df_scored is None or df_scored.empty:
    st.warning("Database tables not found. Run the initial ETL to populate MySQL.")
    if st.button("Initialize Database"):
        with st.spinner("Generating raw data and populating MySQL..."):
            generate_data.main()
            etl.run_pipeline()
            st.rerun()
    st.stop()

min_date = df_scored["timestamp"].min().date()
max_date = df_scored["timestamp"].max().date()

st.sidebar.markdown("---")
st.sidebar.subheader("Filters")

date_range = st.sidebar.date_input(
    "Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

all_risk_bands = ["High Risk", "Medium Review", "Safe"]
selected_bands = st.sidebar.multiselect(
    "Risk Band",
    options=all_risk_bands,
    default=all_risk_bands
)

all_payment_modes = sorted(df_scored["payment_mode"].unique().tolist())
selected_modes = st.sidebar.multiselect(
    "Payment Mode",
    options=all_payment_modes,
    default=all_payment_modes
)

all_categories = sorted(df_scored["merchant_category"].unique().tolist())
selected_cats = st.sidebar.multiselect(
    "Merchant Category",
    options=all_categories,
    default=all_categories
)

start_d, end_d = (date_range[0], date_range[1]) if isinstance(date_range, (tuple, list)) and len(date_range) == 2 else (min_date, max_date)

mask = (
    (df_scored["timestamp"].dt.date >= start_d) &
    (df_scored["timestamp"].dt.date <= end_d) &
    (df_scored["risk_band"].isin(selected_bands)) &
    (df_scored["payment_mode"].isin(selected_modes)) &
    (df_scored["merchant_category"].isin(selected_cats))
)
filtered_df = df_scored[mask].copy()

st.sidebar.info(
    f"Active records: {len(filtered_df):,} / {len(df_scored):,} "
    f"({len(filtered_df) / len(df_scored) * 100:.1f}%)"
)


# Tabs
tab1, tab2, tab3 = st.tabs([
    "Overview",
    "Flagged Transactions",
    "Data Quality & SQL"
])


# Tab 1: Overview
with tab1:
    st.subheader("Transaction Volume and Risk Summary")
    
    total_volume_inr = filtered_df["amount_inr"].sum() if not filtered_df.empty else 0.0
    total_txns = len(filtered_df)
    
    high_risk_txns = filtered_df[filtered_df["risk_band"] == "High Risk"]
    flagged_count = len(high_risk_txns)
    flagged_fraud_rate = (flagged_count / total_txns * 100.0) if total_txns > 0 else 0.0
    amount_at_risk_inr = high_risk_txns["amount_inr"].sum() if not high_risk_txns.empty else 0.0
    
    dq_score_val = float(df_dq["dq_score_pct"].iloc[0]) if df_dq is not None and not df_dq.empty else 99.0
    quarantined_count = int(df_dq["quarantined_rows"].iloc[0]) if df_dq is not None and not df_dq.empty else len(df_quarantine)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Processed Volume", format_inr(total_volume_inr))
    with c2:
        st.metric("Flagged Fraud Rate", f"{flagged_fraud_rate:.2f}%", f"{flagged_count:,} flagged", delta_color="inverse")
    with c3:
        st.metric("Amount at Risk", format_inr(amount_at_risk_inr))
    with c4:
        st.metric("Data Quality Score", f"{dq_score_val:.1f}%", f"{quarantined_count} quarantined", delta_color="off")

    st.markdown("---")

    st.markdown("#### Daily Flagged Transactions")
    if not filtered_df.empty:
        daily_summary = filtered_df.copy()
        daily_summary["date"] = daily_summary["timestamp"].dt.date
        daily_agg = daily_summary.groupby("date").agg(
            total_txns=("txn_id", "count"),
            high_risk_txns=("risk_band", lambda s: (s == "High Risk").sum()),
            medium_risk_txns=("risk_band", lambda s: (s == "Medium Review").sum())
        ).reset_index()

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Bar(
            x=daily_agg["date"],
            y=daily_agg["total_txns"],
            name="Total Transactions",
            marker_color="#cbd5e1"
        ))
        fig_trend.add_trace(go.Scatter(
            x=daily_agg["date"],
            y=daily_agg["medium_risk_txns"],
            mode="lines",
            name="Medium Review (40-69 pts)",
            line=dict(color="#f59e0b", width=2)
        ))
        fig_trend.add_trace(go.Scatter(
            x=daily_agg["date"],
            y=daily_agg["high_risk_txns"],
            mode="lines+markers",
            name="High Risk (>=70 pts)",
            line=dict(color="#ef4444", width=2),
            marker=dict(size=5, color="#ef4444")
        ))
        fig_trend.update_layout(
            template="plotly_white",
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(title="Date"),
            yaxis=dict(title="Transaction Count")
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("No transaction records match the active filter criteria.")

    c_left, c_right = st.columns(2)
    with c_left:
        st.markdown("#### Fraud Rate by Merchant Category")
        if not filtered_df.empty:
            cat_agg = filtered_df.groupby("merchant_category").agg(
                total_cnt=("txn_id", "count"),
                high_risk_cnt=("risk_band", lambda s: (s == "High Risk").sum())
            ).reset_index()
            cat_agg["fraud_rate_pct"] = (cat_agg["high_risk_cnt"] / cat_agg["total_cnt"] * 100.0).round(2)
            cat_agg = cat_agg.sort_values("fraud_rate_pct", ascending=True)

            fig_cat = px.bar(
                cat_agg,
                x="fraud_rate_pct",
                y="merchant_category",
                orientation="h",
                color="fraud_rate_pct",
                color_continuous_scale="Reds",
                labels={"fraud_rate_pct": "High Risk Rate (%)", "merchant_category": "Category"},
                text="fraud_rate_pct",
                template="plotly_white"
            )
            fig_cat.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_cat.update_layout(
                margin=dict(l=20, r=20, t=20, b=20),
                coloraxis_showscale=False
            )
            st.plotly_chart(fig_cat, use_container_width=True)

    with c_right:
        st.markdown("#### Exposure by Payment Mode")
        if not filtered_df.empty:
            mode_agg = filtered_df.groupby("payment_mode").agg(
                total_vol=("amount_inr", "sum"),
                risk_vol=("amount_inr", lambda s: s[filtered_df.loc[s.index, "risk_band"] == "High Risk"].sum())
            ).reset_index()

            fig_mode = px.pie(
                mode_agg,
                names="payment_mode",
                values="risk_vol",
                hole=0.45,
                color_discrete_sequence=["#ef4444", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6"],
                template="plotly_white"
            )
            fig_mode.update_traces(
                textposition="inside",
                textinfo="percent+label",
                hovertemplate="<b>%{label}</b><br>Amount at Risk: Rs %{value:,.0f}<br>Share: %{percent}<extra></extra>"
            )
            fig_mode.update_layout(margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_mode, use_container_width=True)


# Tab 2: Flagged Transactions
with tab2:
    st.subheader("High-Risk Queue and User History")
    st.caption("Review flagged transactions and inspect the user's recent history")

    triage_candidates = filtered_df[filtered_df["risk_band"] == "High Risk"].sort_values(
        by=["risk_score", "amount_inr"], ascending=[False, False]
    ).reset_index(drop=True)

    if triage_candidates.empty:
        st.success("No High-Risk transactions found for the selected filters.")
    else:
        st.write(f"{len(triage_candidates):,} transactions flagged for review:")
        
        display_cols = [
            "txn_id", "user_id", "user_name", "amount_inr", "risk_score",
            "reason_code", "timestamp", "merchant_name", "payment_mode"
        ]
        
        formatted_table = triage_candidates[display_cols].copy()
        formatted_table["amount_formatted"] = formatted_table["amount_inr"].apply(lambda v: f"Rs {v:,.2f}")
        formatted_table["timestamp_str"] = formatted_table["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

        txn_options = [
            f"{row.txn_id} | Score: {row.risk_score} | Rs {row.amount_inr:,.2f} | {row.user_name} ({row.user_id})"
            for _, row in triage_candidates.iterrows()
        ]

        selected_item = st.selectbox(
            "Select transaction to inspect details:",
            options=txn_options,
            index=0
        )
        selected_txn_id = selected_item.split(" | ")[0].strip()

        st.dataframe(
            formatted_table[[
                "txn_id", "user_id", "user_name", "amount_formatted",
                "risk_score", "reason_code", "timestamp_str", "merchant_name", "payment_mode"
            ]].rename(columns={
                "txn_id": "Txn ID",
                "user_id": "User ID",
                "user_name": "Customer Name",
                "amount_formatted": "Amount (INR)",
                "risk_score": "Risk Score",
                "reason_code": "Triggered Rules",
                "timestamp_str": "Timestamp",
                "merchant_name": "Merchant",
                "payment_mode": "Payment Mode"
            }),
            use_container_width=True,
            height=260
        )

        st.markdown("---")

        txn_record = triage_candidates[triage_candidates["txn_id"] == selected_txn_id].iloc[0]
        curr_user_id = txn_record["user_id"]

        st.markdown(f"#### Investigation: `{selected_txn_id}`")
        
        i1, i2, i3 = st.columns(3)
        with i1:
            st.markdown(f"""
            **User Profile**
            - User ID: `{txn_record['user_id']}`
            - Name: {txn_record['user_name']}
            - City: {txn_record['user_city']}
            - KYC Tier: {txn_record['kyc_tier']}
            - Monthly Spend Avg: {format_inr(txn_record['avg_monthly_spend_inr'])}
            """)
        with i2:
            st.markdown(f"""
            **Transaction Details**
            - Amount: **Rs {txn_record['amount_inr']:,.2f}**
            - Merchant: {txn_record['merchant_name']}
            - Category: {txn_record['merchant_category']} (Risk: {txn_record['merchant_risk_tier']})
            - Payment Mode: {txn_record['payment_mode']}
            - Timestamp: {txn_record['timestamp']}
            """)
        with i3:
            st.markdown(f"""
            **Risk Assessment**
            - Risk Score: **{txn_record['risk_score']} / 100**
            - User Average Spend: Rs {float(txn_record['user_avg_amount']):,.2f}
            - 5-Min Velocity: {txn_record['txns_last_5min']} txns
            - Band: <span class="badge-high">{txn_record['risk_band']}</span>
            """, unsafe_allow_html=True)

        st.markdown("**Rule Status**")
        r1, r2, r3, r4 = st.columns(4)
        with r1:
            if txn_record["rule_1_score"] > 0:
                st.error(f"Rule 1 triggered (+40)\nSpike > 3x average (Rs {float(txn_record['user_avg_amount']):,.2f})")
            else:
                st.info("Rule 1: Normal amount")
        with r2:
            if txn_record["rule_2_score"] > 0:
                st.error(f"Rule 2 triggered (+35)\nVelocity >= 4 in 5 min ({txn_record['txns_last_5min']} txns)")
            else:
                st.info("Rule 2: Normal velocity")
        with r3:
            if txn_record["rule_3_score"] > 0:
                st.error("Rule 3 triggered (+15)\nLate night (1-4 AM) > Rs 10k")
            else:
                st.info("Rule 3: Standard hours")
        with r4:
            if txn_record["rule_4_score"] > 0:
                st.error(f"Rule 4 triggered (+10)\nHigh risk category ({txn_record['merchant_category']})")
            else:
                st.info("Rule 4: Standard merchant")

        st.markdown(f"#### Recent Transactions for User `{curr_user_id}`")
        engine = etl.get_engine(include_db=True)
        with engine.connect() as con:
            user_history = pd.read_sql_query(text(f"""
                SELECT 
                    txn_id,
                    timestamp,
                    amount_inr,
                    merchant_name,
                    merchant_category,
                    payment_mode,
                    risk_score,
                    risk_band,
                    reason_code
                FROM scored_transactions_table
                WHERE user_id = '{curr_user_id}'
                ORDER BY timestamp DESC
                LIMIT 10;
            """), con)

        if not user_history.empty:
            user_history["amount_inr"] = user_history["amount_inr"].astype(float)
            user_history["formatted_amount"] = user_history["amount_inr"].apply(lambda v: f"Rs {v:,.2f}")
            
            def highlight_selected(row):
                if row["txn_id"] == selected_txn_id:
                    return ["background-color: #fee2e2; font-weight: bold;"] * len(row)
                return [""] * len(row)

            st.dataframe(
                user_history.style.apply(highlight_selected, axis=1),
                use_container_width=True
            )

            fig_user_trend = px.line(
                user_history.sort_values("timestamp"),
                x="timestamp",
                y="amount_inr",
                markers=True,
                title=f"Transaction History for User {curr_user_id}",
                labels={"amount_inr": "Amount (Rs)", "timestamp": "Timestamp"},
                template="plotly_white"
            )
            fig_user_trend.add_hline(
                y=float(txn_record["user_avg_amount"]),
                line_dash="dash",
                line_color="#10b981",
                annotation_text=f"User Average: Rs {float(txn_record['user_avg_amount']):,.2f}"
            )
            fig_user_trend.update_layout(margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_user_trend, use_container_width=True)


# Tab 3: Data Quality & SQL
with tab3:
    st.subheader("Data Quality & SQL Architecture")
    st.caption("Quarantined ingestion rows and underlying MySQL schema")

    st.markdown("#### Ingestion Quality Summary")
    
    total_raw = int(df_dq["total_incoming_rows"].iloc[0]) if df_dq is not None and not df_dq.empty else 10000
    clean_cnt = int(df_dq["clean_rows_loaded"].iloc[0]) if df_dq is not None and not df_dq.empty else 9900
    quar_cnt = int(df_dq["quarantined_rows"].iloc[0]) if df_dq is not None and not df_dq.empty else 100
    score_pct = float(df_dq["dq_score_pct"].iloc[0]) if df_dq is not None and not df_dq.empty else 99.0

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Ingested", f"{total_raw:,}")
    with m2:
        st.metric("Clean Loaded", f"{clean_cnt:,}")
    with m3:
        st.metric("Quarantined", f"{quar_cnt:,}")
    with m4:
        st.metric("Quality Score", f"{score_pct:.2f}%")

    if not df_quarantine.empty:
        quar_reasons = df_quarantine["quarantine_reason"].value_counts().reset_index()
        quar_reasons.columns = ["reason", "count"]

        q_chart, q_table = st.columns([1, 2])
        with q_chart:
            fig_quar = px.pie(
                quar_reasons,
                names="reason",
                values="count",
                title="Quarantine Reason Breakdown",
                template="plotly_white",
                hole=0.4
            )
            fig_quar.update_layout(margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig_quar, use_container_width=True)

        with q_table:
            st.dataframe(
                df_quarantine[[
                    "quarantine_id", "txn_id", "user_id", "merchant_id",
                    "amount_inr", "quarantine_reason", "quarantined_at"
                ]],
                use_container_width=True,
                height=260
            )

    st.markdown("---")

    st.markdown("#### Database Tables in MySQL")
    engine = etl.get_engine(include_db=True)
    with engine.connect() as con:
        tables_df = pd.read_sql_query(text("SHOW TABLES;"), con)
        table_stats = []
        for tbl in tables_df.iloc[:, 0].tolist():
            cnt = con.execute(text(f"SELECT COUNT(*) FROM `{tbl}`;")).fetchone()[0]
            table_stats.append({"Table Name": tbl, "Rows": cnt, "Type": "View" if "view" in tbl or tbl == "scored_transactions" else "Base Table"})
        st.dataframe(pd.DataFrame(table_stats), use_container_width=True)

    schema_sql_path = etl.get_sql_path("schema.sql")
    if os.path.exists(schema_sql_path):
        with open(schema_sql_path, "r", encoding="utf-8") as f:
            ddl_code = f.read()
        with st.expander("Star Schema DDL (sql/schema.sql)", expanded=False):
            st.code(ddl_code, language="sql")

    fraud_rules_path = etl.get_sql_path("fraud_rules.sql")
    if os.path.exists(fraud_rules_path):
        with open(fraud_rules_path, "r", encoding="utf-8") as f:
            rules_sql = f.read()
        with st.expander("Fraud Scoring SQL (sql/fraud_rules.sql)", expanded=True):
            st.code(rules_sql, language="sql")

    st.markdown("#### SQL Query Runner")
    default_query = """SELECT 
    txn_id,
    user_name,
    amount_inr,
    user_avg_amount,
    txns_last_5min,
    risk_score,
    risk_band,
    reason_code
FROM scored_transactions_table
WHERE risk_score >= 70
ORDER BY amount_inr DESC
LIMIT 5;"""

    query_input = st.text_area("Query input", value=default_query, height=140)
    if st.button("Execute Query"):
        engine = etl.get_engine(include_db=True)
        try:
            with engine.connect() as con:
                res_df = pd.read_sql_query(text(query_input), con)
            st.dataframe(res_df, use_container_width=True)
            st.success(f"Returned {len(res_df)} rows.")
        except Exception as e:
            st.error(f"SQL Error: {e}")
