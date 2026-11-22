import os
import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Fixed seed for consistent local testing
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

CITIES = [
    "Mumbai", "Bengaluru", "Delhi NCR", "Hyderabad", "Chennai",
    "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Lucknow",
    "Chandigarh", "Surat", "Kochi", "Indore", "Bhopal"
]

FIRST_NAMES = [
    "Aarav", "Aditi", "Amit", "Ananya", "Aryan", "Deepak", "Divya", "Gaurav",
    "Ishaan", "Kavya", "Manish", "Neha", "Nikhil", "Pooja", "Pranav", "Priya",
    "Rahul", "Rakesh", "Riya", "Rohan", "Sanjay", "Shreya", "Siddharth", "Sneha",
    "Suresh", "Tanvi", "Varun", "Vikram", "Vivek", "Zoya"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Gupta", "Reddy", "Iyer", "Nair", "Deshmukh",
    "Mehta", "Joshi", "Bhat", "Chakraborty", "Roy", "Banerjee", "Singh",
    "Kumar", "Aggarwal", "Mishra", "Pandey", "Kulkarni", "Shah", "Kapoor"
]

MERCHANTS = [
    ("M_GROC_01", "Blinkit Instant Mart", "Groceries", "Low"),
    ("M_GROC_02", "BigBasket Fresh", "Groceries", "Low"),
    ("M_GROC_03", "Zepto Superfast Delivery", "Groceries", "Low"),
    ("M_GROC_04", "Swiggy Instamart", "Groceries", "Low"),
    ("M_FOOD_01", "Swiggy Gourmet", "Food & Dining", "Low"),
    ("M_FOOD_02", "Zomato Dining & Delivery", "Food & Dining", "Low"),
    ("M_FOOD_03", "Domino's Pizza India", "Food & Dining", "Low"),
    ("M_FOOD_04", "Chai Point Express", "Food & Dining", "Low"),
    ("M_UTIL_01", "Tata Power Mumbai Bills", "Utilities & Bill Pay", "Low"),
    ("M_UTIL_02", "BESCOM Electricity Online", "Utilities & Bill Pay", "Low"),
    ("M_UTIL_03", "Jio Prepaid & Fiber", "Utilities & Bill Pay", "Low"),
    ("M_UTIL_04", "Airtel Payments Bank Bills", "Utilities & Bill Pay", "Low"),
    ("M_ECOM_01", "Amazon India Marketplace", "E-Commerce", "Low"),
    ("M_ECOM_02", "Flipkart Wholesale & Retail", "E-Commerce", "Low"),
    ("M_ECOM_03", "Myntra Fashion Online", "E-Commerce", "Low"),
    ("M_ECOM_04", "Nykaa Beauty & Wellness", "E-Commerce", "Low"),
    ("M_ECOM_05", "Meesho Direct Commerce", "E-Commerce", "Low"),
    ("M_ELEC_01", "Croma Mega Retail", "Electronics", "Medium"),
    ("M_ELEC_02", "Reliance Digital Flagship", "Electronics", "Medium"),
    ("M_ELEC_03", "Vijay Sales Electronics", "Electronics", "Medium"),
    ("M_ELEC_04", "Apple Store BKC Mumbai", "Electronics", "Medium"),
    ("M_TRAV_01", "MakeMyTrip Flights & Hotels", "Travel & Ticketing", "Medium"),
    ("M_TRAV_02", "IRCTC Rail Connect", "Travel & Ticketing", "Medium"),
    ("M_TRAV_03", "IndiGo Airline Direct", "Travel & Ticketing", "Medium"),
    ("M_TRAV_04", "redBus Intercity Express", "Travel & Ticketing", "Medium"),
    ("M_P2P_01", "PhonePe Peer Remit", "Peer-to-Peer Transfer", "Medium"),
    ("M_P2P_02", "GooglePay UPI QuickSend", "Peer-to-Peer Transfer", "Medium"),
    ("M_P2P_03", "Paytm Wallet Cashout", "Peer-to-Peer Transfer", "Medium"),
    ("M_CRYP_01", "CoinSwitch Kuber Global", "Cryptocurrency & Forex", "High"),
    ("M_CRYP_02", "CoinDCX Pro Desk", "Cryptocurrency & Forex", "High"),
    ("M_CRYP_03", "WazirX OTC Trading", "Cryptocurrency & Forex", "High"),
    ("M_CRYP_04", "ForexFast Remit Express", "Cryptocurrency & Forex", "High"),
    ("M_GAME_01", "Stake Online Gaming Arena", "Gaming & Gambling", "High"),
    ("M_GAME_02", "WinRummy Pro League", "Gaming & Gambling", "High"),
    ("M_GAME_03", "Dream11 Super Contests", "Gaming & Gambling", "High"),
    ("M_GAME_04", "PokerBaazi High Stakes", "Gaming & Gambling", "High"),
    ("M_LUX_01", "Tanishq Solitaire Studio", "Jewelry", "High"),
    ("M_LUX_02", "Kalyan Diamonds Haute", "Jewelry", "High"),
    ("M_LUX_03", "Malabar Gold & Diamonds Luxe", "Jewelry", "High"),
]

PAYMENT_MODES = ["UPI", "Credit Card", "Debit Card", "Net Banking", "Wallet"]
PAYMENT_WEIGHTS = [0.65, 0.15, 0.10, 0.06, 0.04]

KYC_TIERS = ["Tier 1 - Full KYC", "Tier 2 - Minimum KYC", "Tier 3 - eKYC"]
KYC_WEIGHTS = [0.55, 0.30, 0.15]


def generate_users(num_users=1000):
    users = []
    for i in range(1, num_users + 1):
        uid = f"USR_{i:05d}"
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        city = random.choice(CITIES)
        account_age = int(np.random.gamma(shape=3.0, scale=120) + 30)
        account_age = min(max(account_age, 30), 1800)
        kyc = random.choices(KYC_TIERS, weights=KYC_WEIGHTS)[0]
        
        # Monthly spend baseline based roughly on KYC tier
        base_spend = 15000 if "Full" in kyc else (8000 if "eKYC" in kyc else 4000)
        monthly_spend = float(round(np.random.lognormal(mean=np.log(base_spend), sigma=0.6), -2))
        monthly_spend = max(3000.0, min(monthly_spend, 250000.0))
        
        users.append({
            "user_id": uid,
            "name": name,
            "city": city,
            "account_age_days": account_age,
            "kyc_tier": kyc,
            "avg_monthly_spend_inr": monthly_spend
        })
    return pd.DataFrame(users)


def generate_merchants():
    merchants = []
    for m_id, name, cat, risk in MERCHANTS:
        merchants.append({
            "merchant_id": m_id,
            "merchant_name": name,
            "category": cat,
            "risk_tier": risk
        })
    return pd.DataFrame(merchants)


def generate_transactions(users_df, merchants_df, total_txns=10000):
    end_date = datetime(2026, 11, 21, 23, 59, 59)
    start_date = end_date - timedelta(days=60)
    total_seconds = int((end_date - start_date).total_seconds())

    user_ids = users_df["user_id"].tolist()
    user_spend_map = dict(zip(users_df["user_id"], users_df["avg_monthly_spend_inr"]))
    user_city_map = dict(zip(users_df["user_id"], users_df["city"]))
    
    low_risk = merchants_df[merchants_df["risk_tier"] == "Low"]["merchant_id"].tolist()
    med_risk = merchants_df[merchants_df["risk_tier"] == "Medium"]["merchant_id"].tolist()
    high_risk = merchants_df[merchants_df["risk_tier"] == "High"]["merchant_id"].tolist()

    txns = []
    txn_counter = 1

    # Injected counts: ~5% fraud (~500 rows) and ~1% messy (~100 rows)
    burst_groups = 70
    spike_count = 100
    night_count = 100
    normal_count = total_txns - (burst_groups * 4) - spike_count - night_count

    # 1. Normal everyday transactions
    for _ in range(normal_count):
        uid = random.choice(user_ids)
        typical_avg = max(150.0, user_spend_map[uid] / 25.0)
        
        amount = float(round(np.random.lognormal(mean=np.log(typical_avg), sigma=0.55), 2))
        amount = max(25.0, min(amount, typical_avg * 2.2))
        
        t_stamp = start_date + timedelta(seconds=random.randint(0, total_seconds))
        # Bias normal transactions towards daytime hours
        if t_stamp.hour in [1, 2, 3, 4] and random.random() < 0.90:
            t_stamp = t_stamp.replace(hour=random.randint(8, 22))

        if random.random() < 0.85:
            mid = random.choice(low_risk)
        elif random.random() < 0.80:
            mid = random.choice(med_risk)
        else:
            mid = random.choice(high_risk)
            amount = min(amount, 2500.0)

        pay_mode = random.choices(PAYMENT_MODES, weights=PAYMENT_WEIGHTS)[0]
        device = f"DEV_{hash(uid) % 10000:04d}"
        city = user_city_map[uid] if random.random() < 0.92 else random.choice(CITIES)

        txns.append({
            "txn_id": f"TXN_{txn_counter:07d}",
            "user_id": uid,
            "merchant_id": mid,
            "amount_inr": amount,
            "timestamp": t_stamp.strftime("%Y-%m-%d %H:%M:%S"),
            "payment_mode": pay_mode,
            "device_id": device,
            "city": city
        })
        txn_counter += 1

    # 2. Fraud pattern A: velocity bursts (4-5 transactions in 5 minutes with escalating amounts)
    for _ in range(burst_groups):
        uid = random.choice(user_ids)
        burst_size = random.randint(4, 5)
        base_time = start_date + timedelta(seconds=random.randint(0, total_seconds - 3600))
        mid = random.choice(high_risk if random.random() < 0.6 else med_risk)
        device = f"DEV_FRAUD_{random.randint(100, 999)}"
        normal_avg = user_spend_map[uid] / 25.0
        
        if random.random() < 0.35:
            base_time = base_time.replace(hour=random.choice([1, 2, 3]))
            
        for step in range(burst_size):
            step_time = base_time + timedelta(seconds=step * random.randint(25, 55))
            amt = float(round(max(normal_avg * random.uniform(4.0, 9.0), 12500.0), 2)) if step >= 3 else float(round(random.uniform(2500.0, 7500.0), 2))
                
            txns.append({
                "txn_id": f"TXN_{txn_counter:07d}",
                "user_id": uid,
                "merchant_id": mid,
                "amount_inr": amt,
                "timestamp": step_time.strftime("%Y-%m-%d %H:%M:%S"),
                "payment_mode": random.choice(["UPI", "Credit Card"]),
                "device_id": device,
                "city": random.choice(CITIES)
            })
            txn_counter += 1

    # 3. Fraud pattern B: isolated high-value spending spikes (>3x user normal spend)
    for _ in range(spike_count):
        uid = random.choice(user_ids)
        normal_avg = user_spend_map[uid] / 25.0
        spike_amt = float(round(max(normal_avg * random.uniform(4.5, 12.0), 22000.0), 2))
        t_stamp = start_date + timedelta(seconds=random.randint(0, total_seconds))
        mid = random.choice(high_risk if random.random() < 0.65 else med_risk)
        
        txns.append({
            "txn_id": f"TXN_{txn_counter:07d}",
            "user_id": uid,
            "merchant_id": mid,
            "amount_inr": spike_amt,
            "timestamp": t_stamp.strftime("%Y-%m-%d %H:%M:%S"),
            "payment_mode": random.choice(["Credit Card", "UPI", "Net Banking"]),
            "device_id": f"DEV_SUSP_{random.randint(1000, 9999)}",
            "city": random.choice(CITIES)
        })
        txn_counter += 1

    # 4. Fraud pattern C: late-night high-value drain (1-4 AM and > Rs 10,000)
    for _ in range(night_count):
        uid = random.choice(user_ids)
        t_stamp = start_date + timedelta(
            days=random.randint(0, 58),
            hours=random.choice([1, 2, 3]),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59)
        )
        amt = float(round(random.uniform(14000.0, 95000.0), 2))
        mid = random.choice(high_risk if random.random() < 0.70 else med_risk)

        txns.append({
            "txn_id": f"TXN_{txn_counter:07d}",
            "user_id": uid,
            "merchant_id": mid,
            "amount_inr": amt,
            "timestamp": t_stamp.strftime("%Y-%m-%d %H:%M:%S"),
            "payment_mode": random.choice(["Credit Card", "Net Banking", "UPI"]),
            "device_id": f"DEV_NIGHT_{random.randint(1000, 9999)}",
            "city": random.choice(CITIES)
        })
        txn_counter += 1

    df_txns = pd.DataFrame(txns)
    df_txns["dt"] = pd.to_datetime(df_txns["timestamp"])
    df_txns = df_txns.sort_values("dt").reset_index(drop=True)
    df_txns = df_txns.drop(columns=["dt"])
    
    # Ensure exact row target
    if len(df_txns) > total_txns:
        df_txns = df_txns.iloc[:total_txns].copy()
    elif len(df_txns) < total_txns:
        deficit = total_txns - len(df_txns)
        extra = df_txns.sample(deficit, replace=True).copy()
        df_txns = pd.concat([df_txns, extra], ignore_index=True)

    df_txns["txn_id"] = [f"TXN_{i+1:07d}" for i in range(len(df_txns))]

    # 5. Inject 1% messy records (exactly 100 rows) for quarantine testing
    all_indices = list(range(len(df_txns)))
    random.shuffle(all_indices)
    
    # Null merchant IDs (34 rows)
    for idx in all_indices[:34]:
        df_txns.at[idx, "merchant_id"] = None

    # Duplicate transaction IDs (33 rows)
    target_dups = random.sample(all_indices[100:1000], 33)
    for idx, source_idx in zip(all_indices[34:67], target_dups):
        df_txns.at[idx, "txn_id"] = df_txns.at[source_idx, "txn_id"]

    # Negative / zero amounts (33 rows)
    for idx in all_indices[67:100]:
        df_txns.at[idx, "amount_inr"] = float(random.choice([-2500.0, -850.0, -12000.0, 0.0, -450.0]))

    export_cols = ["txn_id", "user_id", "merchant_id", "amount_inr", "timestamp", "payment_mode", "device_id", "city"]
    return df_txns[export_cols]


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_dir = os.path.join(base_dir, "data", "raw")
    os.makedirs(raw_dir, exist_ok=True)

    print("Generating 1,000 synthetic Indian users...")
    users_df = generate_users(1000)
    users_df.to_csv(os.path.join(raw_dir, "users.csv"), index=False)

    print("Generating 39 merchant nodes...")
    merchants_df = generate_merchants()
    merchants_df.to_csv(os.path.join(raw_dir, "merchants.csv"), index=False)

    print("Generating 10,000 transactions (5% fraud patterns, 1% messy rows)...")
    txns_df = generate_transactions(users_df, merchants_df, total_txns=10000)
    txns_df.to_csv(os.path.join(raw_dir, "transactions.csv"), index=False)

    print(f"Data generation complete. Saved CSV files to {raw_dir}")


if __name__ == "__main__":
    main()
