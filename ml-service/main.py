"""
╔══════════════════════════════════════════════════════════════════╗
║  DEPRECATED — Development Stub Only                            ║
║                                                                ║
║  This file is a mock API for local development/testing ONLY.   ║
║  The canonical production entrypoint is:                       ║
║                                                                ║
║      ml-service/service/main.py                                ║
║                                                                ║
║  The Dockerfile and docker-compose use service/main.py via:    ║
║      uvicorn service.main:app                                  ║
║                                                                ║
║  Do NOT deploy this file in production.                        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import warnings
warnings.warn(
    "ml-service/main.py is a DEPRECATED development stub. "
    "Use 'uvicorn service.main:app' for the real API.",
    DeprecationWarning,
    stacklevel=2
)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import uvicorn

app = FastAPI(title="Sentinel ML Service (DEPRECATED STUB)")

class FeatureVector(BaseModel):
    endpoint: str
    hour_sin: float
    hour_cos: float
    dow_sin: float
    dow_cos: float
    week_of_year: float
    is_weekend: float
    is_holiday: float
    day_of_month: float
    req_rate_1m: float
    req_rate_5m: float
    req_rate_15m: float
    req_rate_30m: float
    latency_std_5m: float
    latency_std_15m: float
    req_max_5m: float
    req_max_15m: float
    ewma_03: float
    ewma_07: float
    rate_of_change: float
    autocorr_lag1: float
    cpu_util: float
    memory_pressure: float
    active_connections: float
    cache_hit_ratio: float
    replica_count: float
    queue_depth: float

class PredictionResponse(BaseModel):
    predicted_load: float
    confidence: float
    action: str

class AnomalyResponse(BaseModel):
    is_anomaly: bool
    anomaly_score: float

@app.get("/health")
def health():
    return {"status": "healthy", "service": "ml-service"}

@app.post("/predict", response_model=PredictionResponse)
def predict(features: FeatureVector):
    # Mock prediction - replace with actual XGBoost model
    predicted_load = features.req_rate_1m * 1.2
    confidence = 0.85
    action = "SCALE_UP" if predicted_load > 100 else "MAINTAIN"
    
    return PredictionResponse(
        predicted_load=predicted_load,
        confidence=confidence,
        action=action
    )

@app.post("/anomaly", response_model=AnomalyResponse)
def detect_anomaly(features: FeatureVector):
    # Mock anomaly detection - replace with Isolation Forest
    anomaly_score = abs(features.rate_of_change) * 10
    is_anomaly = anomaly_score > 50
    
    return AnomalyResponse(
        is_anomaly=is_anomaly,
        anomaly_score=anomaly_score
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
