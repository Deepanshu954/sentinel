# Service: ML Service (Python/FastAPI)

The ML Service provides the predictive power for the Sentinel platform. It serves XGBoost and Isolation Forest models for request rate prediction and anomaly detection.

## Purpose
- **Predictive Scaling**: XGBoost Regressor predicts future (5-minute) request rates based on historical data.
- **Anomaly Detection**: Isolation Forest identifies irregular traffic spikes or patterns.
- **Health Checks**: Transparently reports model loading and versions.

## WHERE is the code?
- **FastAPI Core**: `ml-service/service/main.py`
- **Model Handlers**: `ml-service/service/models.py`
- **Training Scripts**: `ml-service/ml/train_xgboost.py`, `ml-service/ml/train_isolation_forest.py`
- **Synthetic Data**: `ml-service/scripts/generate_training_data.py`
- **Multi-Source Builder**: `ml-service/scripts/build_multisource_training_data.py`
- **Dataset Adapters**: `ml-service/scripts/adapters/` (wikimedia, azure, google_cluster, alibaba, apache_access)
- **Dataset Manifest**: `ml-service/scripts/dataset_manifest.json`
- **Quality Checks**: `ml-service/scripts/data_quality.py`

## Data Ingestion Pipeline
Sentinel supports two training data paths:

### Legacy (Synthetic)
```bash
bash scripts/train.sh
```
Uses `prepare_dataset.py` → synthetic 30-day traffic → `training_data.parquet`.

### Multi-Source (Research-Grade)
```bash
USE_MULTISOURCE_DATA=1 bash scripts/train.sh
```
Uses `build_multisource_training_data.py` with manifest-driven adapter dispatch:
1. Reads `dataset_manifest.json` for enabled sources
2. Dispatches each source to a typed adapter (Wikimedia, Azure, Google, Alibaba)
3. Normalizes all sources to `(timestamp UTC, value float)` format
4. Fuses sources using `sum` or `weighted_mean` mode
5. Engineers 26 features from the composite series
6. Generates `dataset_quality_report.json` pre-training
7. Outputs `training_data.parquet`

See **[Dataset Preparation Guide](DATASET_PREP_GUIDE.md)** for full details.

## Features (26-Vector Order)
The Orchestrator MUST send features in this exact order for the XGBoost and Isolation Forest models to function correctly:

1.  **Temporal**: `hour_sin`, `hour_cos`, `dow_sin`, `dow_cos`, `week_of_year`, `is_weekend`, `is_holiday`, `day_of_month`.
2.  **Statistical**: `req_rate_1m`, `req_rate_5m`, `req_rate_15m`, `req_rate_30m`, `latency_std_5m`, `latency_std_15m`, `req_max_5m`, `req_max_15m`, `ewma_03`, `ewma_07`, `rate_of_change`, `autocorr_lag1`.
3.  **Infra**: `cpu_util`, `memory_pressure`, `active_connections`, `cache_hit_ratio`, `replica_count`, `queue_depth`.

## Dependencies
- **Scikit-learn / XGBoost**: core libraries for inference.
- **Pydantic**: data validation for the 26-feature vector.
- **Prometheus**: scrapes prediction latency and anomaly scores.

## Safe/Dangerous Changes
- **[SAFE]**: Updating the API response structure with non-breaking metadata.
- **[DANGEROUS]**: Replacing model weights (`.json`, `.pkl`) with incompatible versions or changing the 26-feature input order.

## Red Flags
- **`models_loaded: false`**: Model weight files are missing or corrupted. Run `./scripts/train.sh`.
- **High Prediction Latency**: Scrutinize `sentinel_ml_prediction_latency_seconds`.
- **422 Unprocessable Entity**: The Orchestrator is sending a malformed or incorrectly sized feature vector.
