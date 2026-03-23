#!/usr/bin/env python3
import os
import sys
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

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
    
    # Chronological 80/20 split, NO shuffle
    split_idx = int(len(df) * 0.8)
    
    X_train = df[FEATURES].iloc[:split_idx]
    y_train = df['future_req_rate_5m'].iloc[:split_idx]
    X_test = df[FEATURES].iloc[split_idx:]
    y_test = df['future_req_rate_5m'].iloc[split_idx:]
    
    print(f"Training on {len(X_train)} samples, testing on {len(X_test)} samples.")
    
    # XGBRegressor main
    print("Training main predictor...")
    model_main = xgb.XGBRegressor(
        n_estimators=200, 
        max_depth=8, 
        learning_rate=0.1, 
        subsample=0.8, 
        random_state=42
    )
    model_main.fit(X_train, y_train)
    
    # XGBRegressor lower
    print("Training lower quantile bound (0.1)...")
    model_lower = xgb.XGBRegressor(
        objective='reg:quantileerror', 
        quantile_alpha=0.1,
        n_estimators=200, 
        max_depth=8, 
        learning_rate=0.1, 
        subsample=0.8, 
        random_state=42
    )
    model_lower.fit(X_train, y_train)
    
    # XGBRegressor upper
    print("Training upper quantile bound (0.9)...")
    model_upper = xgb.XGBRegressor(
        objective='reg:quantileerror', 
        quantile_alpha=0.9,
        n_estimators=200, 
        max_depth=8, 
        learning_rate=0.1, 
        subsample=0.8, 
        random_state=42
    )
    model_upper.fit(X_train, y_train)
    
    # Evaluate
    preds = model_main.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    mse = mean_squared_error(y_test, preds)
    rmse = np.sqrt(mse)
    
    print("\n--- Model Evaluation ---")
    print(f"MAE: {mae:.2f}")
    if mae < 15.0:
        print("PERFORMANCE: MAE < 15% Target achieved.")
    print(f"RMSE: {rmse:.2f}")
    
    # Save
    os.makedirs(MODELS_DIR, exist_ok=True)
    
    main_path = os.path.join(MODELS_DIR, 'xgb_model.json')
    lower_path = os.path.join(MODELS_DIR, 'xgb_lower.json')
    upper_path = os.path.join(MODELS_DIR, 'xgb_upper.json')
    
    model_main.save_model(main_path)
    model_lower.save_model(lower_path)
    model_upper.save_model(upper_path)
    
    print(f"\nSaved models to {MODELS_DIR}")
    
if __name__ == '__main__':
    main()
