import pandas as pd
import numpy as np
import os

def generate_data():
    np.random.seed(42)
    print("Generating 30 days of 1-second interval timestamps...")
    # 30 days * 24 * 60 * 60 = 2,592,000 rows
    dates = pd.date_range(start="2024-01-01", periods=2592000, freq='S')
    
    print("Modeling synthetic request rates...")
    req_count = np.full(2592000, 10.0)
    
    df = pd.DataFrame(index=dates)
    
    hour = df.index.hour
    dayofweek = df.index.dayofweek
    
    # Base multipliers
    # Business hours: 8 to 18 on weekdays
    business_mask = (hour >= 8) & (hour <= 18) & (dayofweek < 5)
    req_count[business_mask] *= 3.0
    
    # Night valley: 2 to 6
    night_mask = (hour >= 2) & (hour <= 6)
    req_count[night_mask] *= 0.2
    
    # Weekend: whole day
    weekend_mask = (dayofweek >= 5)
    req_count[weekend_mask] *= 0.6
    
    # Noise +- 15%
    req_count *= np.random.uniform(0.85, 1.15, size=2592000)
    
    is_surge = np.zeros(2592000)
    
    # 5 random surges
    for _ in range(5):
        surge_idx = np.random.randint(0, 2592000 - 2400)
        surge_len = np.random.randint(1200, 2400) # 20 to 40 mins
        multiplier = np.random.uniform(5.0, 10.0)
        req_count[surge_idx:surge_idx+surge_len] *= multiplier
        is_surge[surge_idx:surge_idx+surge_len] = 1.0

    df['req_count'] = req_count
    df['is_surge'] = is_surge
    
    print("Computing Temporal Features...")
    df['hour_sin'] = np.sin(2 * np.pi * df.index.hour / 24.0)
    df['hour_cos'] = np.cos(2 * np.pi * df.index.hour / 24.0)
    df['dow_sin'] = np.sin(2 * np.pi * df.index.dayofweek / 7.0)
    df['dow_cos'] = np.cos(2 * np.pi * df.index.dayofweek / 7.0)
    df['week_of_year'] = df.index.isocalendar().week.astype(float)
    df['is_weekend'] = (df.index.dayofweek >= 5).astype(float)
    df['is_holiday'] = 0.0
    df['day_of_month'] = df.index.day.astype(float)
    
    print("Computing Statistical Features (Moving Averages & Max)...")
    df['req_rate_1m'] = df['req_count'].rolling(60, min_periods=1).mean()
    df['req_rate_5m'] = df['req_count'].rolling(300, min_periods=1).mean()
    df['req_rate_15m'] = df['req_count'].rolling(900, min_periods=1).mean()
    df['req_rate_30m'] = df['req_count'].rolling(1800, min_periods=1).mean()
    df['req_max_5m'] = df['req_count'].rolling(300, min_periods=1).max()
    df['req_max_15m'] = df['req_count'].rolling(900, min_periods=1).max()
    
    print("Computing Statistical Features (Latencies)...")
    base_latency = np.random.uniform(10.0, 50.0, size=2592000)
    base_latency[is_surge == 1.0] *= np.random.uniform(2.0, 5.0)
    df['latency'] = base_latency
    df['latency_std_5m'] = df['latency'].rolling(300, min_periods=1).std().fillna(0)
    df['latency_std_15m'] = df['latency'].rolling(900, min_periods=1).std().fillna(0)
    
    print("Computing Statistical Features (EWMA, ROC, Autocorr)...")
    df['ewma_03'] = df['req_rate_1m'].ewm(alpha=0.3, adjust=False).mean()
    df['ewma_07'] = df['req_rate_1m'].ewm(alpha=0.7, adjust=False).mean()
    df['rate_of_change'] = (df['req_rate_1m'] - df['req_rate_1m'].shift(1)).fillna(0) / np.maximum(df['req_rate_1m'].shift(1).fillna(0), 1.0)
    df['autocorr_lag1'] = df['req_rate_1m'].rolling(60).corr(df['req_rate_1m'].shift(1)).fillna(0)
    
    print("Setting Infra Features...")
    df['cpu_util'] = 0.45
    df['memory_pressure'] = 0.45
    df['active_connections'] = 1.0
    df['cache_hit_ratio'] = 0.5
    df['replica_count'] = 1.0
    df['queue_depth'] = 0.0
    
    print("Computing Target Label (future_req_rate_5m)...")
    # rolling mean evaluated up to index i, shifted backwards by 300 makes it the future 5m 
    df['future_req_rate_5m'] = df['req_count'].rolling(300, min_periods=1).mean().shift(-300)
    
    # Drop rows at tails that don't have valid future windows
    df.dropna(inplace=True)
    
    feature_columns = [
        'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos', 'week_of_year',
        'is_weekend', 'is_holiday', 'day_of_month', 'req_rate_1m', 'req_rate_5m',
        'req_rate_15m', 'req_rate_30m', 'latency_std_5m', 'latency_std_15m',
        'req_max_5m', 'req_max_15m', 'ewma_03', 'ewma_07', 'rate_of_change',
        'autocorr_lag1', 'cpu_util', 'memory_pressure', 'active_connections',
        'cache_hit_ratio', 'replica_count', 'queue_depth'
    ]
    
    final_cols = feature_columns + ['future_req_rate_5m', 'is_surge']
    df_final = df[final_cols].astype(np.float32)
    
    os.makedirs('data', exist_ok=True)
    out_path = 'data/training_data.parquet'
    print(f"Saving to {out_path} ...")
    df_final.to_parquet(out_path, engine='pyarrow')
    
    print("\n--- Summary Statistics ---")
    print(f"Total Rows: {len(df_final)}")
    print(f"Number of Features: {len(feature_columns)}")
    print(df_final[['req_rate_1m', 'future_req_rate_5m', 'is_surge']].describe())
    print("Done!")

if __name__ == "__main__":
    generate_data()
