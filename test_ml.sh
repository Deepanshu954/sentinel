#!/bin/bash
# tests the newly built ML Microservice endpoints

echo "======================================"
echo "    Sentinel ML Endpoint Tests      "
echo "======================================"

echo -e "\n[1] Checking /health ..."
curl -s http://localhost:8000/health | grep -o '.*'

echo -e "\n\n[2] Checking /predict ..."
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [0.5, 0.5, 0.5, 0.5, 12, 0, 0, 15, 10.5, 11.2, 11.0, 11.0, 15.0, 20.0, 30.0, 35.0, 10.5, 10.5, 0.1, 0.8, 0.45, 0.45, 1.0, 0.5, 1.0, 0.0]}' | grep -o '.*'

echo -e "\n\n[3] Checking /anomaly ..."
curl -s -X POST http://localhost:8000/anomaly \
  -H "Content-Type: application/json" \
  -d '{"features": [0.5, 0.5, 0.5, 0.5, 12, 0, 0, 15, 10.5, 11.2, 11.0, 11.0, 15.0, 20.0, 30.0, 35.0, 10.5, 10.5, 0.1, 0.8, 0.45, 0.45, 1.0, 0.5, 1.0, 0.0]}' | grep -o '.*'

echo -e "\n\n[4] Checking /metrics (Prometheus) ..."
curl -s http://localhost:8000/metrics | head -n 10
echo "..."
echo -e "\n======================================"
