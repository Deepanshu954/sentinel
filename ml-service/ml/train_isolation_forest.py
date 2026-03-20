import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score
import pickle
import os

def train():
    print("Loading data...")
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Path to data folder relative to script (../data)
    data_path = os.path.join(script_dir, '..', 'data', 'training_data.parquet')
    
    df = pd.read_parquet(data_path)
    
    features = [
        'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos', 'week_of_year',
        'is_weekend', 'is_holiday', 'day_of_month', 'req_rate_1m', 'req_rate_5m',
        'req_rate_15m', 'req_rate_30m', 'latency_std_5m', 'latency_std_15m',
        'req_max_5m', 'req_max_15m', 'ewma_03', 'ewma_07', 'rate_of_change',
        'autocorr_lag1', 'cpu_util', 'memory_pressure', 'active_connections',
        'cache_hit_ratio', 'replica_count', 'queue_depth'
    ]
    
    print("Chronological split (80/20)...")
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    
    print("Filtering NORMAL traffic for training...")
    X_train_normal = train_df[train_df['is_surge'] == 0][features]
    
    X_test = test_df[features]
    y_test_true = test_df['is_surge']
    
    print("Training IsolationForest...")
    clf = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
    clf.fit(X_train_normal)
    
    print("Evaluating...")
    preds = clf.predict(X_test)
    y_pred_anomaly = (preds == -1).astype(int)
    
    precision = precision_score(y_test_true, y_pred_anomaly, zero_division=0)
    recall = recall_score(y_test_true, y_pred_anomaly, zero_division=0)
    
    print(f"Precision on test surge events: {precision:.4f}")
    print(f"Recall on test surge events: {recall:.4f}")
    
    models_dir = os.path.join(script_dir, '..', 'models')
    os.makedirs(models_dir, exist_ok=True)
    model_path = os.path.join(models_dir, 'isolation_forest.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(clf, f)
        
    print("Done!")

if __name__ == '__main__':
    train()
