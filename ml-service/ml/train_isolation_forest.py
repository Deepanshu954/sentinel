#!/usr/bin/env python3
import os
import sys
import pandas as pd
import numpy as np
import pickle
from sklearn.ensemble import IsolationForest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MI_SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
DATA_PATH = os.path.join(MI_SERVICE_DIR, "data", "processed", "training_data.parquet")
MODELS_DIR = os.path.join(MI_SERVICE_DIR, "model_weights")

FEATURES = [
    'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos', 'week_of_year',
    'is_weekend', 'is_holiday', 'day_of_month', 'req_rate_1m', 'req_rate_5m',
    'req_rate_15m', 'req_rate_30m', 'latency_std_5m', 'latency_std_15m',
    'req_max_5m', 'req_max_15m', 'ewma_03', 'ewma_07', 'rate_of_change',
    'autocorr_lag1', 'cpu_util', 'memory_pressure', 'active_connections',
    'cache_hit_ratio', 'replica_count', 'queue_depth'
]

def main():
    if not os.path.exists(DATA_PATH):
        print(f"ERROR: {DATA_PATH} not found. Run prepare_dataset.py first.")
        sys.exit(1)
        
    print(f"Loading {DATA_PATH}...")
    df = pd.read_parquet(DATA_PATH)
    
    # Chronological 80/20 split
    split_idx = int(len(df) * 0.8)
    
    print("Filtering out surge traffic for pure anomaly training...")
    baseline = df['req_rate_1m'].iloc[:split_idx].median()
    threshold = 3.0 * baseline
    
    # Normal traffic only (exclude surge rows where rate > 3x baseline)
    mask_normal = df['req_rate_1m'].iloc[:split_idx] <= threshold
    
    # Also if synthetic 'is_surge' exists, exclude it
    if 'is_surge' in df.columns:
        mask_normal = mask_normal & (df['is_surge'].iloc[:split_idx] == 0)
        
    X_train_normal = df[FEATURES].iloc[:split_idx][mask_normal]
    
    print(f"Training on {len(X_train_normal)} normal samples (excluded {split_idx - len(X_train_normal)} surges)...")
    
    clf = IsolationForest(
        n_estimators=100, 
        contamination=0.05, 
        random_state=42
    )
    clf.fit(X_train_normal)
    
    # Evaluate conceptually on test
    X_test = df[FEATURES].iloc[split_idx:]
    preds = clf.predict(X_test)
    anomalies = np.sum(preds == -1)
    
    print(f"\n--- Anomaly Evaluation ---")
    print(f"Detected {anomalies} anomalies out of {len(X_test)} test samples ({(anomalies/len(X_test))*100:.2f}%)")
    
    # Save
    os.makedirs(MODELS_DIR, exist_ok=True)
    out_path = os.path.join(MODELS_DIR, 'isolation_forest.pkl')
    with open(out_path, 'wb') as f:
        pickle.dump(clf, f)
        
    print(f"Saved Isolation Forest to {out_path}")

if __name__ == '__main__':
    main()
