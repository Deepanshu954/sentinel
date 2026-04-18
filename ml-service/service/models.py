from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any

class FeatureInput(BaseModel):
    features: List[float] = Field(..., description="Exactly 26 features")

    @field_validator('features')
    def validate_features_length(cls, v):
        if len(v) != 26:
            raise ValueError(f"Features array must be exactly 26 elements long, got {len(v)}")
        return v

class PredictionResponse(BaseModel):
    predicted_req_rate: float
    lower_bound: float
    upper_bound: float
    confidence: float
    action: str  # "DISPATCH" | "HOLD"
    threshold_used: float

class AnomalyResponse(BaseModel):
    is_anomaly: bool
    anomaly_score: float
    interpretation: str  # "normal" | "suspicious" | "anomaly"

class HealthResponse(BaseModel):
    status: str
    models_loaded: bool
    model_count: int
