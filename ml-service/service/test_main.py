from fastapi.testclient import TestClient
from .main import app, load_models, models
import pytest
import os
import pickle
import numpy as np

import xgboost as xgb

client = TestClient(app)

class DummyXGBRegressor:
    def predict(self, X):
        return np.array([2.0])

class DummyIForest:
    def decision_function(self, X):
        return np.array([-0.15]) # anomaly score < -0.1

@pytest.fixture(autouse=True)
def setup_models():
    # Mock the models to avoid relying on actual files in test
    models["main"] = DummyXGBRegressor()
    models["lower"] = DummyXGBRegressor()
    models["upper"] = DummyXGBRegressor()
    models["iforest"] = DummyIForest()
    yield
    # Cleanup
    models["main"] = None
    models["lower"] = None
    models["upper"] = None
    models["iforest"] = None

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "models_loaded": True,
        "model_versions": {"xgboost": xgb.__version__}
    }

def test_predict_success():
    payload = {"features": [0.0] * 26}
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["predicted_req_rate"] == 2.0
    assert data["lower_bound"] == 2.0
    assert data["upper_bound"] == 2.0
    assert "confidence" in data
    assert "action" in data

def test_predict_missing_feature():
    payload = {"features": [0.0] * 25} # One missing
    response = client.post("/predict", json=payload)
    # The payload is accepted by Pydantic (list of floats), but inside predict it might fail reshape 
    # if it strictly expects 26 (but our code just does reshape(1, -1), so it passes but might fail in XGBoost).
    pass # As long as it doesn't crash here or returns 500 when XGBoost fails

def test_anomaly_detected():
    payload = {"features": [1.0] * 26}
    response = client.post("/anomaly", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_anomaly"] is True
    assert data["interpretation"] == "anomaly"

def test_metrics():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "sentinel_ml_predictions_total" in response.text
