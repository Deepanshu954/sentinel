import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import os

def train():
    print("Loading data...")
    df = pd.read_parquet('../data/training_data.parquet')
    
    features = [
        'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos', 'week_of_year',
        'is_weekend', 'is_holiday', 'day_of_month', 'req_rate_1m', 'req_rate_5m',
        'req_rate_15m', 'req_rate_30m', 'latency_std_5m', 'latency_std_15m',
        'req_max_5m', 'req_max_15m', 'ewma_03', 'ewma_07', 'rate_of_change',
        'autocorr_lag1', 'cpu_util', 'memory_pressure', 'active_connections',
        'cache_hit_ratio', 'replica_count', 'queue_depth'
    ]
    target = 'future_req_rate_5m'
    
    print("Chronological split (80/20)...")
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    
    X_train, y_train = train_df[features], train_df[target]
    X_test, y_test = test_df[features], test_df[target]
    
    print("Training Main XGBRegressor...")
    model_main = xgb.XGBRegressor(
        n_estimators=200, max_depth=8, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8, random_state=42
    )
    model_main.fit(X_train, y_train)
    
    print("Evaluating Main Model...")
    preds = model_main.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = mean_squared_error(y_test, preds, squared=False)
    r2 = r2_score(y_test, preds)
    
    print(f"MAE: {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"R2: {r2:.4f}")
    
    print("Training Quantile Models (q=0.1, q=0.9)...")
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
    
    print("Saving models...")
    os.makedirs('../models', exist_ok=True)
    model_main.save_model('../models/xgb_model.json')
    model_lower.save_model('../models/xgb_lower.json')
    model_upper.save_model('../models/xgb_upper.json')
    print("Done!")

if __name__ == '__main__':
    train()
