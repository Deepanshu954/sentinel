# Sentinel — Developer Documentation

Complete reference for the Sentinel Intelligent API Observability & Auto-Scaling Platform.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Data Flow](#data-flow)
3. [Environment Variables](#environment-variables)
4. [Kafka Topics & Schemas](#kafka-topics--schemas)
5. [Feature Vector (26 Features)](#feature-vector-26-features)
6. [ML Models](#ml-models)
7. [Confidence Gate](#confidence-gate)
8. [API Reference](#api-reference)
9. [Service Details](#service-details)
10. [Development Workflow](#development-workflow)
11. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

Sentinel is a **6-service distributed backend** with 3 supporting infrastructure services:

| # | Service | Language | Role |
|---|---------|----------|------|
| 1 | **Gateway** | Go 1.22 | Authenticates requests (JWT), rate-limits (Redis), publishes events to Kafka |
| 2 | **Kafka** | Confluent 7.6 (KRaft) | Message broker — no Zookeeper needed |
| 3 | **Orchestrator** | Java 21 / Spring Boot 3.3 | Runs Kafka Streams for feature extraction, calls ML service, dispatches scaling actions |
| 4 | **ML Service** | Python 3.11 / FastAPI | Serves XGBoost predictions and Isolation Forest anomaly detection |
| 5 | **InfluxDB** | 2.7 | Time-series storage for feature vectors |
| 6 | **PostgreSQL** | 16 | Audit log for scaling actions |
| 7 | **Redis** | 7 | Rate limiting state + scaling action pub/sub |
| 8 | **Prometheus** | 2.51 | Metrics scraping from Gateway + ML Service |
| 9 | **Grafana** | 10.4 | 7-panel monitoring dashboard |

---

## Data Flow

```
Client Request
     │
     ▼
┌─────────┐   JWT Auth    ┌──────┐   Rate Limit   ┌──────────┐
│ Gateway  │─────────────►│Redis │◄──────────────│ Token    │
│  :8080   │              │:6379 │               │ Bucket   │
└────┬─────┘              └──────┘               └──────────┘
     │ Publish JSON event
     ▼
┌──────────┐  api.events   ┌──────────────────────────────────┐
│  Kafka   │──────────────►│ Orchestrator Kafka Streams       │
│  :9092   │               │ ┌─ 26-feature extraction        │
│          │◄──────────────│ └─ Writes to api.features topic  │
│          │  api.features │                                   │
└──────────┘               └─────────┬────────────────────────┘
                                     │
                    ┌────────────────┬┘
                    │                │
                    ▼                ▼
           ┌──────────────┐  ┌──────────────┐
           │  InfluxDB    │  │ ML Service   │
           │  :8086       │  │ :8000        │
           │ (features)   │  │ /predict     │
           └──────────────┘  │ /anomaly     │
                             └──────┬───────┘
                                    │ prediction response
                                    ▼
                          ┌─────────────────────┐
                          │ PredictionScheduler  │
                          │ ConfidenceGate       │
                          │ ActionDispatcher     │
                          └─────────┬───────────┘
                                    │
                         ┌──────────┼──────────┐
                         ▼          ▼          ▼
                      Redis     PostgreSQL   Logs
                    (pub/sub)  (audit log)
```

**Cycle:** Every 5 seconds, the PredictionScheduler:
1. Queries InfluxDB for latest feature vectors
2. Calls ML Service `/predict` endpoint
3. ConfidenceGate evaluates: C ≥ 0.75 → DISPATCH, else HOLD
4. ActionDispatcher publishes result to Redis pub/sub + PostgreSQL audit

---

## Environment Variables

All variables are set in `.env` (copy from `.env.example`). Docker Compose reads them automatically.

| Variable | Default | Used By |
|----------|---------|---------|
| `JWT_SECRET` | `sentinel-super-secret-jwt-key-change-in-prod` | Gateway |
| `INFLUX_TOKEN` | `sentinel-influx-admin-token` | Gateway, Orchestrator, ML Service |
| `INFLUX_ORG` | `sentinel` | Gateway, Orchestrator |
| `INFLUX_BUCKET` | `sentinel-metrics` | Gateway, Orchestrator |
| `INFLUX_URL` | `http://influxdb:8086` | Gateway, Orchestrator, ML Service |
| `REDIS_ADDR` | `redis:6379` | Gateway, Orchestrator |
| `KAFKA_BROKERS` | `kafka:9092` | Gateway, Orchestrator, ML Service |
| `RATE_LIMIT_PER_MIN` | `1000` | Gateway |
| `CONFIDENCE_THRESHOLD` | `0.75` | Orchestrator |
| `ML_SERVICE_URL` | `http://ml-service:8000` | Orchestrator |
| `POSTGRES_USER` | `sentinel` | PostgreSQL |
| `POSTGRES_PASSWORD` | `sentinel123` | PostgreSQL, Orchestrator |
| `POSTGRES_DB` | `sentinel` | PostgreSQL, Orchestrator |

---

## Kafka Topics & Schemas

### `api.events` — Raw Request Metadata

Published by the Gateway for every authenticated request.

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

### `api.features` — Feature Vectors

Published by Kafka Streams after computing rolling statistics per endpoint.

```json
{
  "endpoint": "/api/test",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_count": 45,
  "latency_avg": 12.5,
  "req_rate_1m": 15.0,
  "hour_sin": 0.707,
  "hour_cos": 0.707,
  ...
}
```

### `scaling.actions` — (Future)

Reserved for dispatch directives from the orchestrator.

---

## Feature Vector (26 Features)

The Kafka Streams topology computes 26 features grouped into 3 categories:

### Temporal (8)

| # | Feature | Description |
|---|---------|-------------|
| 1 | `hour_sin` | sin(2π × hour/24) |
| 2 | `hour_cos` | cos(2π × hour/24) |
| 3 | `dow_sin` | sin(2π × day_of_week/7) |
| 4 | `dow_cos` | cos(2π × day_of_week/7) |
| 5 | `week_of_year` | ISO week number |
| 6 | `is_weekend` | 1.0 if Saturday/Sunday |
| 7 | `is_holiday` | 1.0 if major holiday |
| 8 | `day_of_month` | Day (1–31) |

### Statistical (12)

| # | Feature | Description |
|---|---------|-------------|
| 9 | `req_rate_1m` | Requests per minute (1-min window) |
| 10 | `req_rate_5m` | Requests per minute (5-min window) |
| 11 | `req_rate_15m` | Requests per minute (15-min window) |
| 12 | `req_rate_30m` | Requests per minute (30-min window) |
| 13 | `latency_std_5m` | Latency standard deviation (5-min) |
| 14 | `latency_std_15m` | Latency standard deviation (15-min) |
| 15 | `req_max_5m` | Max requests in 5-min window |
| 16 | `req_max_15m` | Max requests in 15-min window |
| 17 | `ewma_03` | Exponentially weighted moving avg (α=0.3) |
| 18 | `ewma_07` | Exponentially weighted moving avg (α=0.7) |
| 19 | `rate_of_change` | First derivative of request rate |
| 20 | `autocorr_lag1` | Lag-1 autocorrelation |

### Infrastructure State (6)

| # | Feature | Description |
|---|---------|-------------|
| 21 | `cpu_util` | CPU utilization % |
| 22 | `memory_pressure` | Memory usage % |
| 23 | `active_connections` | Active connection count |
| 24 | `cache_hit_ratio` | Redis cache hit ratio |
| 25 | `replica_count` | Current replica count |
| 26 | `queue_depth` | Message queue depth |

---

## ML Models

### XGBoost Regressor

- **Task:** Predict future 5-minute request rate
- **Training data:** 30-day synthetic data (~2.5M rows) with realistic patterns
- **Performance:** MAE ~1.08
- **Model files:** `ml-service/models/xgb_model.json`, `xgb_lower.json`, `xgb_upper.json`
- **Quantile bounds:** 90% confidence interval (lower/upper)

### Isolation Forest

- **Task:** Detect anomalous traffic patterns
- **Training:** Fitted on normal traffic only; anomalies score below threshold
- **Model file:** `ml-service/models/isolation_forest.pkl`
- **Output:** `is_anomaly` (bool), `anomaly_score` (float), `interpretation` (string)

### Re-training

```bash
# Train from host (requires Python 3.9+ with dependencies)
python3 scripts/train_models.py

# Or train inside container
make train
```

Model files are gitignored — `launch.sh` auto-trains if missing.

---

## Confidence Gate

From the linked research paper: *Optimizing API Performance Using AI-Based Predictive Request Management*

```
C = 1 − (σ_pred / μ_pred)
```

- `μ_pred` = predicted request rate (XGBoost output)
- `σ_pred` = prediction uncertainty (derived from upper/lower quantile bounds)
- **Threshold τ = 0.75**
  - `C ≥ 0.75` → **DISPATCH** (scaling action executed)
  - `C < 0.75` → **HOLD** (prediction too uncertain)

---

## API Reference

### Gateway (:8080)

#### `GET /health`
```bash
curl http://localhost:8080/health
```
```json
{"service": "sentinel-gateway", "status": "ok"}
```

#### `GET /api/*` (authenticated)
```bash
TOKEN=$(python3 scripts/generate_jwt.py)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/products
```
- **401** — Missing/invalid JWT
- **429** — Rate limit exceeded (1000 req/min)
- **502** — No upstream backend (auth passed)

#### `GET /metrics`
Prometheus metrics endpoint. Key metrics:
- `sentinel_gateway_requests_total` — Total request count
- `sentinel_gateway_request_duration_seconds` — Latency histogram

### ML Service (:8000)

#### `GET /health`
```bash
curl http://localhost:8000/health
```
```json
{"status": "ok", "models_loaded": true, "model_versions": {"xgboost": "2.0.3"}}
```

#### `POST /predict`
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [0.5,0.5,0.5,0.5,12,0,0,15,10,11,11,11,15,20,30,35,10,10,0.1,0.8,0.5,0.5,1,0.5,1,0]}'
```
Response:
```json
{
  "predicted_req_rate": 12.259,
  "lower_bound": 18.651,
  "upper_bound": 20.345,
  "confidence": 0.861,
  "action": "DISPATCH",
  "threshold_used": 0.75
}
```

#### `POST /anomaly`
```bash
curl -X POST http://localhost:8000/anomaly \
  -H "Content-Type: application/json" \
  -d '{"features": [50,50,50,50,120,0,0,150,1000,900,800,700,55,60,1500,1600,920,940,1.5,7.5,95,92,2000,0.2,10,50]}'
```
Response:
```json
{"is_anomaly": true, "anomaly_score": -0.045, "interpretation": "anomaly"}
```

#### `GET /metrics`
Prometheus metrics. Key metric: `sentinel_ml_prediction_latency_seconds`

### Orchestrator (:8090)

#### `GET /api/actions`
```bash
curl http://localhost:8090/api/actions
```
Returns recent scaling decisions from PostgreSQL audit log.

---

## Service Details

### Gateway (Go)

| File | Purpose |
|------|---------|
| `main.go` | HTTP server, routing, middleware chain |
| `middleware/auth.go` | JWT validation using HMAC-SHA256 |
| `middleware/ratelimit.go` | Sliding-window rate limiter (Redis-backed) |
| `middleware/logging.go` | Request/response logging |
| `kafka/producer.go` | Publishes events to `api.events` topic |
| `metrics/prometheus.go` | Registers Prometheus counters & histograms |

### Orchestrator (Spring Boot)

| Package | Purpose |
|---------|---------|
| `stream/` | Kafka Streams topology — 26-feature extraction |
| `client/` | `MLServiceClient` (REST), `InfluxDBReader` (Flux queries) |
| `scheduler/` | `PredictionScheduler` — polls every 5s |
| `gate/` | `ConfidenceGate` — applies confidence threshold |
| `dispatcher/` | `ActionDispatcher` — Redis pub/sub + PostgreSQL audit |

### ML Service (Python)

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app entry point |
| `service/main.py` | Route handlers for /predict, /anomaly, /health |
| `service/models.py` | Pydantic request/response models |
| `ml/train_xgboost.py` | XGBoost training script |
| `ml/train_isolation_forest.py` | Isolation Forest training script |
| `ml/feature_validator.py` | Feature validation utilities |
| `scripts/generate_training_data.py` | Synthetic data generator (30-day) |

---

## Development Workflow

### Modifying a service

1. Edit source code in the service directory
2. Rebuild & restart just that service:
   ```bash
   ./sentinel.sh build <service-name>
   # Example: ./sentinel.sh build ml-service
   ```
3. Check logs:
   ```bash
   ./sentinel.sh logs <service-name>
   ```
4. Run validation:
   ```bash
   ./sentinel.sh test
   ```

### Adding a new API endpoint to Gateway

1. Add route in `gateway/main.go`
2. Add any middleware in `gateway/middleware/`
3. Update Prometheus metrics if needed in `gateway/metrics/`
4. Rebuild: `./sentinel.sh build gateway`

### Adding a new ML endpoint

1. Add route handler in `ml-service/service/main.py`
2. Add Pydantic models in `ml-service/service/models.py`
3. Rebuild: `./sentinel.sh build ml-service`

### Regenerating training data

```bash
cd ml-service && python3 scripts/generate_training_data.py
python3 ml/train_xgboost.py
python3 ml/train_isolation_forest.py
```

Or use the combined script: `python3 scripts/train_models.py`

---

## Troubleshooting

### Services not starting

```bash
# Check service status
docker compose ps

# Check specific service logs
docker compose logs <service-name>

# Restart a specific service
docker compose restart <service-name>
```

### Kafka not healthy

Kafka takes 30–60s to initialize in KRaft mode. If it's stuck:
```bash
docker compose restart kafka
sleep 30
docker compose ps
```

### InfluxDB has no data

1. Check the orchestrator is publishing features:
   ```bash
   docker compose logs orchestrator | grep -i "influx\|feature"
   ```
2. Check api.features topic has messages:
   ```bash
   docker exec sentinel-kafka kafka-get-offsets --bootstrap-server localhost:9092 --topic api.features
   ```

### ML models missing

Models are gitignored. They auto-train on launch, or manually:
```bash
python3 scripts/train_models.py
```

### Gateway returns 502

This is **expected** — it means JWT auth passed but there's no upstream backend. The gateway is designed as a reverse proxy; in this project the upstream doesn't exist since we're only observing the gateway's behavior.

### Rate limited (429)

Default: 1000 req/min per client. To change:
```bash
# In .env
RATE_LIMIT_PER_MIN=5000
# Then restart
./sentinel.sh restart
```

### Grafana shows no data

1. Verify Prometheus is scraping targets: http://localhost:9090/targets
2. Verify InfluxDB has data: http://localhost:8086 (login: `admin` / `sentinel-influx-password`)
3. Check dashboard datasource configuration at http://localhost:3000

### Docker memory issues

Sentinel needs ~3 GB RAM. On Docker Desktop, go to Settings → Resources → increase memory to ≥4 GB.

---

## InfluxDB Schema

| Field | Type | Description |
|-------|------|-------------|
| **Measurement** | `api_features` | — |
| **Tags** | `endpoint` (string) | API path |
| **Fields** | All 26 feature names | float64 |
| **Timestamp** | nanosecond precision | — |
| **Retention** | 15 days | — |

### Query examples (Flux)

```flux
// Latest features for all endpoints
from(bucket: "sentinel-metrics")
  |> range(start: -15m)
  |> filter(fn: (r) => r._measurement == "api_features")

// Request rate for specific endpoint
from(bucket: "sentinel-metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "api_features")
  |> filter(fn: (r) => r._field == "req_rate_1m")
  |> filter(fn: (r) => r.endpoint == "/api/test")
```
