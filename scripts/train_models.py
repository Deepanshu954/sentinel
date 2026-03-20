#!/usr/bin/env python3
"""
Sentinel ML Model Training Script
Generates synthetic data and trains all required models:
  - XGBoost Regressor (main + quantile bounds)
  - Isolation Forest (anomaly detection)
"""

import sys
import os
import numpy as np

# Add ml-service to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
ML_SERVICE_DIR = os.path.join(PROJECT_DIR, "ml-service")

sys.path.insert(0, ML_SERVICE_DIR)

def check_dependencies():
    """Check that required packages are installed."""
    missing = []
    for pkg in ["numpy", "pandas", "xgboost", "sklearn"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"Missing packages: {', '.join(missing)}")
        print(f"Install with: pip3 install {' '.join(missing)}")
        sys.exit(1)

def train_all():
    check_dependencies()

    import pandas as pd
    import xgboost as xgb
    from sklearn.ensemble import IsolationForest
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, precision_score, recall_score
    import pickle

    models_dir = os.path.join(ML_SERVICE_DIR, "models")
    data_dir = os.path.join(ML_SERVICE_DIR, "data")
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    FEATURES = [
        'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos', 'week_of_year',
        'is_weekend', 'is_holiday', 'day_of_month', 'req_rate_1m', 'req_rate_5m',
        'req_rate_15m', 'req_rate_30m', 'latency_std_5m', 'latency_std_15m',
        'req_max_5m', 'req_max_15m', 'ewma_03', 'ewma_07', 'rate_of_change',
        'autocorr_lag1', 'cpu_util', 'memory_pressure', 'active_connections',
        'cache_hit_ratio', 'replica_count', 'queue_depth'
    ]

    # ── Step 1: Generate synthetic training data ─────────────────
    data_path = os.path.join(data_dir, "training_data.parquet")
    if os.path.exists(data_path):
        print(f"[1/4] Loading existing training data from {data_path}")
        df = pd.read_parquet(data_path)
    else:
        print("[1/4] Generating 10K synthetic training samples (26 features)...")
        np.random.seed(42)
        N = 10000

        hours = np.random.uniform(0, 24, N)
        dows = np.random.randint(0, 7, N)

        data = {
            'hour_sin':           np.sin(2 * np.pi * hours / 24.0),
            'hour_cos':           np.cos(2 * np.pi * hours / 24.0),
            'dow_sin':            np.sin(2 * np.pi * dows / 7.0),
            'dow_cos':            np.cos(2 * np.pi * dows / 7.0),
            'week_of_year':       np.random.uniform(1, 52, N),
            'is_weekend':         (dows >= 5).astype(float),
            'is_holiday':         np.random.choice([0.0, 1.0], N, p=[0.95, 0.05]),
            'day_of_month':       np.random.randint(1, 31, N).astype(float),
        }

        # Base request rates with daily pattern
        base_rate = 50 + 40 * np.sin(2 * np.pi * hours / 24.0 - np.pi/2)
        base_rate *= np.where(dows >= 5, 0.6, 1.0)
        noise = np.random.normal(0, 5, N)
        req_rate_1m = np.maximum(base_rate + noise, 1.0)

        data['req_rate_1m']   = req_rate_1m
        data['req_rate_5m']   = req_rate_1m * np.random.uniform(0.9, 1.1, N)
        data['req_rate_15m']  = req_rate_1m * np.random.uniform(0.85, 1.15, N)
        data['req_rate_30m']  = req_rate_1m * np.random.uniform(0.8, 1.2, N)
        data['latency_std_5m']  = np.random.exponential(5, N)
        data['latency_std_15m'] = np.random.exponential(6, N)
        data['req_max_5m']    = req_rate_1m * np.random.uniform(1.2, 2.0, N)
        data['req_max_15m']   = req_rate_1m * np.random.uniform(1.3, 2.5, N)
        data['ewma_03']       = req_rate_1m * np.random.uniform(0.8, 1.0, N)
        data['ewma_07']       = req_rate_1m * np.random.uniform(0.9, 1.0, N)
        data['rate_of_change'] = np.random.normal(0, 0.3, N)
        data['autocorr_lag1']  = np.random.uniform(0.5, 1.0, N)
        data['cpu_util']       = np.random.uniform(0.1, 0.9, N)
        data['memory_pressure'] = np.random.uniform(0.1, 0.8, N)
        data['active_connections'] = np.random.randint(10, 500, N).astype(float)
        data['cache_hit_ratio']    = np.random.uniform(0.3, 0.95, N)
        data['replica_count']      = np.random.choice([1.0, 2.0, 3.0], N)
        data['queue_depth']        = np.random.exponential(3, N)

        # Target: future request rate (with lag correlation)
        data['future_req_rate_5m'] = req_rate_1m * np.random.uniform(0.8, 1.3, N) + noise * 0.5

        # Surge labels for anomaly model
        is_surge = np.zeros(N)
        surge_idx = np.random.choice(N, size=int(N * 0.05), replace=False)
        is_surge[surge_idx] = 1.0
        for feat in ['req_rate_1m', 'req_rate_5m', 'req_rate_15m', 'req_max_5m']:
            data[feat][surge_idx] *= np.random.uniform(3.0, 8.0, len(surge_idx))
        data['future_req_rate_5m'][surge_idx] *= np.random.uniform(3.0, 8.0, len(surge_idx))
        data['is_surge'] = is_surge

        df = pd.DataFrame(data).astype(np.float32)
        df.to_parquet(data_path)
        print(f"  Saved {N} samples to {data_path}")

    print(f"  Dataset: {len(df)} samples, {len(FEATURES)} features")

    # ── Step 2: Train XGBoost models ─────────────────────────────
    print("\n[2/4] Training XGBoost models...")
    split = int(len(df) * 0.8)
    X_train, y_train = df[FEATURES].iloc[:split], df['future_req_rate_5m'].iloc[:split]
    X_test,  y_test  = df[FEATURES].iloc[split:], df['future_req_rate_5m'].iloc[split:]

    # Main model
    model_main = xgb.XGBRegressor(
        n_estimators=200, max_depth=8, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8, random_state=42
    )
    model_main.fit(X_train, y_train)
    preds = model_main.predict(X_test)
    mae  = mean_absolute_error(y_test, preds)
    rmse = mean_squared_error(y_test, preds, squared=False)
    r2   = r2_score(y_test, preds)
    print(f"  Main Model  — MAE: {mae:.2f}  RMSE: {rmse:.2f}  R²: {r2:.4f}")

    # Quantile models
    model_lower = xgb.XGBRegressor(
        objective='reg:quantileerror', quantile_alpha=0.1,
        n_estimators=200, max_depth=8, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8, random_state=42
    )
    model_lower.fit(X_train, y_train)

    model_upper = xgb.XGBRegressor(
        objective='reg:quantileerror', quantile_alpha=0.9,
        n_estimators=200, max_depth=8, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8, random_state=42
    )
    model_upper.fit(X_train, y_train)
    print("  Quantile bounds (q=0.1, q=0.9) trained")

    model_main.save_model(os.path.join(models_dir, 'xgb_model.json'))
    model_lower.save_model(os.path.join(models_dir, 'xgb_lower.json'))
    model_upper.save_model(os.path.join(models_dir, 'xgb_upper.json'))
    print("  Saved: xgb_model.json, xgb_lower.json, xgb_upper.json")

    # ── Step 3: Train Isolation Forest ───────────────────────────
    print("\n[3/4] Training Isolation Forest (anomaly detection)...")
    X_train_normal = df[df['is_surge'] == 0][FEATURES].iloc[:split]

    clf = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
    clf.fit(X_train_normal)

    X_test_all = df[FEATURES].iloc[split:]
    y_true = df['is_surge'].iloc[split:]
    y_pred = (clf.predict(X_test_all) == -1).astype(int)

    prec = precision_score(y_true, y_pred, zero_division=0)
    rec  = recall_score(y_true, y_pred, zero_division=0)
    print(f"  Precision: {prec:.4f}  Recall: {rec:.4f}")

    with open(os.path.join(models_dir, 'isolation_forest.pkl'), 'wb') as f:
        pickle.dump(clf, f)
    print("  Saved: isolation_forest.pkl")

    # ── Summary ──────────────────────────────────────────────────
    print("\n[4/4] Training Complete!")
    print("=" * 50)
    print(f"  XGBoost MAE:      {mae:.2f}")
    print(f"  XGBoost R²:       {r2:.4f}")
    print(f"  Anomaly Precision: {prec:.4f}")
    print(f"  Anomaly Recall:    {rec:.4f}")
    print(f"  Models saved to:   {models_dir}/")
    print("=" * 50)

if __name__ == '__main__':
    train_all()
