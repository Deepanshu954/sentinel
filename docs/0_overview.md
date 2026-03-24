# Sentinel — Project Overview

Sentinel is an intelligent API observability and auto-scaling platform that uses machine learning to predict traffic surges and anomaly detection to secure the system.

## WHAT does this do?
Sentinel observes incoming API traffic, extracts complex features (rolling averages, seasonality, error rates), and coordinates with ML models to decide when to scale up OR down BEFORE a performance bottleneck occurs.

## WHERE is the code?
The system is divided into three primary services and supporting infrastructure:
- **Gateway** (Go): `/gateway`
- **Orchestrator** (Java/Spring): `/orchestrator`
- **ML Service** (Python): `/ml-service`
- **Infrastructure**: `/infra` (Prometheus, Grafana configuration)

## High-Level Data Flow
1. **Request Ingestion**: [Gateway](service_gateway.md) receives requests, checks JWT/Rate-limit, and logs metadata to Kafka (`api.events`).
2. **Feature Extraction**: [Orchestrator](service_orchestrator.md) consumes raw events, computes 26 features, and writes to InfluxDB + Kafka (`api.features`).
3. **ML Inference**: Orchestrator triggers [ML Service](service_ml.md) for request rate prediction (XGBoost) and anomaly detection (Isolation Forest).
4. **Action Dispatch**: If confidence ≥ 0.75, scaling actions are published to Redis and logged in PostgreSQL.

## Kafka Topic Schemas

### `api.events` (Raw JSON)
```json
{
  "ts": 1700000000000,
  "endpoint": "/api/products",
  "method": "GET",
  "client_id": "user-abc",
  "latency_ms": 23,
  "status": 200,
  "bytes_sent": 1024
}
```

### `api.features` (Windowed Aggregates)
Includes 26 calculated features + metadata:
```json
{
  "endpoint": "/api/test",
  "timestamp": "2024-03-24T12:00:00Z",
  "req_rate_1m": 45.0,
  "latency_avg_5m": 12.5,
  ...
}
```

## Red Flags (System-Wide)
- **Validation Score < 30/30**: Run `./scripts/validate_sentinel.sh` immediately.
- **InfluxDB Authentication**: Ensure `INFLUX_TOKEN` is synced across all services in `.env`.
- **Kafka Startup**: Kafka takes ~60s to initialize. Services will retry connection.
