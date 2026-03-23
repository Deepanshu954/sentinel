from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel
from typing import List, Optional
import xgboost as xgb
import pickle
import numpy as np
import os
import time

app = FastAPI(title="Sentinel ML Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Schemas
class FeatureInput(BaseModel):
    features: List[float]

class PredictionResponse(BaseModel):
    predicted_req_rate: float
    lower_bound: float
    upper_bound: float
    confidence: float
    action: str
    threshold_used: float

class AnomalyResponse(BaseModel):
    is_anomaly: bool
    anomaly_score: float
    interpretation: str

class HealthResponse(BaseModel):
    status: str
    models_loaded: bool
    model_count: int

# Thread-safe global model references
models = {
    "main": None,
    "lower": None,
    "upper": None,
    "iforest": None
}

# Prometheus Metrics
PREDICTIONS_TOTAL = Counter("sentinel_ml_predictions_total", "Total predictions made")
PREDICTION_LATENCY = Histogram("sentinel_ml_prediction_latency_seconds", "Latency of prediction requests")
CONFIDENCE_SCORE = Gauge("sentinel_ml_confidence_score", "Last prediction confidence score")
ANOMALIES_DETECTED = Counter("sentinel_ml_anomalies_detected_total", "Total anomalies detected")

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.on_event("startup")
def load_models():
    # Resolve correct parent directory regardless of local vs docker context
    root_dir = os.path.dirname(BASE_DIR)
    # Inside docker compose this maps to /app/models
    main_model_path = os.path.join(root_dir, "models", "xgb_model.json")
    lower_model_path = os.path.join(root_dir, "models", "xgb_lower.json")
    upper_model_path = os.path.join(root_dir, "models", "xgb_upper.json")
    iso_model_path = os.path.join(root_dir, "models", "isolation_forest.pkl")
        
    try:
        if os.path.exists(main_model_path):
            m = xgb.XGBRegressor()
            m.load_model(main_model_path)
            m.load_model(main_model_path)
            models["main"] = m
            
        if os.path.exists(lower_model_path):
            l = xgb.XGBRegressor()
            l.load_model(lower_model_path)
            models["lower"] = l
            
        if os.path.exists(upper_model_path):
            u = xgb.XGBRegressor()
            u.load_model(upper_model_path)
            models["upper"] = u
            
        if os.path.exists(iso_model_path):
            with open(iso_model_path, "rb") as f:
                models["iforest"] = pickle.load(f)
                
    except Exception as e:
        print(f"Error loading models: {e}")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc)})

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"error": str(exc)})

@app.post("/predict", response_model=PredictionResponse)
def predict(payload: FeatureInput):
    if not all([models["main"], models["lower"], models["upper"]]):
        return JSONResponse(status_code=503, content={"error": "Models are not loaded or missing."})
        
    start_time = time.time()
    
    if len(payload.features) != 26:
        return JSONResponse(status_code=422, content={"error": f"Must provide exactly 26 features. Got {len(payload.features)}."})
        
    X = np.array(payload.features).reshape(1, -1)
    PREDICTIONS_TOTAL.inc()
    
    main_pred = float(models["main"].predict(X)[0])
    lower_pred = float(models["lower"].predict(X)[0])
    upper_pred = float(models["upper"].predict(X)[0])
    
    # Mathematical confidence bounded [0, 1]
    diff = upper_pred - lower_pred
    C = 1.0 - (diff / max(main_pred, 1.0))
    C = max(0.0, min(1.0, float(C)))
    
    CONFIDENCE_SCORE.set(C)
    action = "DISPATCH" if C >= CONFIDENCE_THRESHOLD else "HOLD"
    
    latency = time.time() - start_time
    PREDICTION_LATENCY.observe(latency)
    
    return PredictionResponse(
        predicted_req_rate=main_pred,
        lower_bound=lower_pred,
        upper_bound=upper_pred,
        confidence=C,
        action=action,
        threshold_used=CONFIDENCE_THRESHOLD
    )

@app.post("/anomaly", response_model=AnomalyResponse)
def detect_anomaly(payload: FeatureInput):
    if not models["iforest"]:
        return JSONResponse(status_code=503, content={"error": "Isolation Forest model is not loaded."})
        
    if len(payload.features) != 26:
        return JSONResponse(status_code=422, content={"error": f"Must provide exactly 26 features. Got {len(payload.features)}."})
        
    X = np.array(payload.features).reshape(1, -1)
    
    # isolation_forest.score_samples(X) 
    score = float(models["iforest"].score_samples(X)[0])
    
    if score > -0.1:
        interpretation = "anomaly"
        is_anomaly = True
        ANOMALIES_DETECTED.inc()
    elif score > -0.2:
        interpretation = "suspicious"
        is_anomaly = False
    else:
        interpretation = "normal"
        is_anomaly = False
        
    return AnomalyResponse(
        is_anomaly=is_anomaly,
        anomaly_score=score,
        interpretation=interpretation
    )

@app.get("/health", response_model=HealthResponse)
def health():
    count = sum(1 for m in models.values() if m is not None)
    return HealthResponse(
        status="ok",
        models_loaded=(count == 4),
        model_count=count
    )

@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
