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
    def score_samples(self, X):
        """Return score > -0.1 to trigger the 'anomaly' branch."""
        return np.array([-0.05])

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
    data = response.json()
    assert data["status"] == "ok"
    assert data["models_loaded"] is True
    assert data["model_count"] == 4

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
    assert data["action"] in ("DISPATCH", "HOLD")

def test_predict_missing_feature():
    payload = {"features": [0.0] * 25}  # One missing
    response = client.post("/predict", json=payload)
    assert response.status_code == 422

def test_predict_extra_feature():
    payload = {"features": [0.0] * 27}  # One extra
    response = client.post("/predict", json=payload)
    assert response.status_code == 422

def test_anomaly_detected():
    payload = {"features": [1.0] * 26}
    response = client.post("/anomaly", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_anomaly"] is True
    assert data["interpretation"] == "anomaly"

def test_anomaly_normal():
    """Test that a score deep below -0.2 is classified as normal."""
    class NormalIForest:
        def score_samples(self, X):
            return np.array([-0.5])
    models["iforest"] = NormalIForest()
    payload = {"features": [0.0] * 26}
    response = client.post("/anomaly", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_anomaly"] is False
    assert data["interpretation"] == "normal"

def test_metrics():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "sentinel_ml_predictions_total" in response.text
