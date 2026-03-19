import numpy as np

EXPECTED_FEATURES = [
    'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos', 'week_of_year',
    'is_weekend', 'is_holiday', 'day_of_month', 'req_rate_1m', 'req_rate_5m',
    'req_rate_15m', 'req_rate_30m', 'latency_std_5m', 'latency_std_15m',
    'req_max_5m', 'req_max_15m', 'ewma_03', 'ewma_07', 'rate_of_change',
    'autocorr_lag1', 'cpu_util', 'memory_pressure', 'active_connections',
    'cache_hit_ratio', 'replica_count', 'queue_depth'
]

def validate_features(feature_dict: dict):
    """
    Validates incoming feature vectors: 26 features, correct types, no NaN/Inf.
    Raises ValueError with specific field name if validation fails.
    """
    if len(feature_dict) != 26:
        raise ValueError(f"Expected exactly 26 features, got {len(feature_dict)}")
        
    for feat in EXPECTED_FEATURES:
        if feat not in feature_dict:
            raise ValueError(f"Missing required feature: {feat}")
            
        val = feature_dict[feat]
        if not isinstance(val, (int, float)):
            raise ValueError(f"Feature {feat} is not numeric type: {type(val)}")
            
        if np.isnan(val):
            raise ValueError(f"Feature {feat} contains NaN")
            
        if np.isinf(val):
            raise ValueError(f"Feature {feat} contains Infinity")
            
    return True
