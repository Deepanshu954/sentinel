from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from .models import FeatureInput, PredictionResponse, AnomalyResponse, HealthResponse
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

# Thread-safe global model references evaluated at startup only
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

@app.on_event("startup")
def load_models():
    try:
        main_model = xgb.XGBRegressor()
        main_model.load_model("models/xgb_model.json")
        models["main"] = main_model
        
        lower_model = xgb.XGBRegressor()
        lower_model.load_model("models/xgb_lower.json")
        models["lower"] = lower_model
        
        upper_model = xgb.XGBRegressor()
        upper_model.load_model("models/xgb_upper.json")
        models["upper"] = upper_model
        
        with open("models/isolation_forest.pkl", "rb") as f:
            models["iforest"] = pickle.load(f)
            
        print("All models loaded successfully!")
    except Exception as e:
        print(f"Error loading models: {e}. Starting anyway to serve 503 errors gracefully.")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
    )

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"error": str(exc)},
    )

@app.post("/predict", response_model=PredictionResponse)
def predict(payload: FeatureInput):
    if not all([models["main"], models["lower"], models["upper"]]):
        return JSONResponse(status_code=503, content={"error": "Models are not loaded or missing."})
        
    start_time = time.time()
    
    # Dimensions match inference payload -> (1, 26) Numpy array DMatrix conversion auto-wrapped by XGBRegressor
    X = np.array(payload.features).reshape(1, -1)
    
    PREDICTIONS_TOTAL.inc()
    
    main_pred = float(models["main"].predict(X)[0])
    lower_pred = float(models["lower"].predict(X)[0])
    upper_pred = float(models["upper"].predict(X)[0])
    
    # Bounds logic
    diff = upper_pred - lower_pred
    confidence = 1.0 - (diff / max(main_pred, 1.0))
    confidence = max(0.0, min(1.0, confidence))
    
    CONFIDENCE_SCORE.set(confidence)
    action = "DISPATCH" if confidence >= CONFIDENCE_THRESHOLD else "HOLD"
    
    latency = time.time() - start_time
    PREDICTION_LATENCY.observe(latency)
    
    return PredictionResponse(
        predicted_req_rate=main_pred,
        lower_bound=lower_pred,
        upper_bound=upper_pred,
        confidence=confidence,
        action=action,
        threshold_used=CONFIDENCE_THRESHOLD
    )

@app.post("/anomaly", response_model=AnomalyResponse)
def detect_anomaly(payload: FeatureInput):
    if not models["iforest"]:
        return JSONResponse(status_code=503, content={"error": "Isolation Forest model is not loaded."})
        
    X = np.array(payload.features).reshape(1, -1)
    score = float(models["iforest"].decision_function(X)[0])
    
    if score > -0.1:
        interpretation = "anomaly"
        is_anomaly = True
        ANOMALIES_DETECTED.inc()
    elif score >= -0.2 and score <= -0.1:
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
    loaded = all(models.values())
    return HealthResponse(
        status="ok",
        models_loaded=loaded,
        model_versions={"xgboost": xgb.__version__}
    )

@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
