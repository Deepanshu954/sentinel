# SENTINEL — Master Context File
# Update this file after every session. Drag into Antigravity at the start of every session.

## PROJECT IDENTITY
Name: Sentinel — Intelligent API Observability & Auto-Scaling Platform
GitHub: https://github.com/Deepanshu954/Sentinel
Developer: Deepanshu Chauhan (E23CSEU1617, Bennett University)
Linked research paper: Optimizing API Performance Using AI-Based Predictive Request Management

## PROJECT PURPOSE
Sentinel is a 6-service distributed backend platform that:
- Acts as an intelligent API gateway (Go) with JWT auth and token-bucket rate limiting
- Streams all request metadata to Apache Kafka
- Computes 26 rolling statistical features via Kafka Streams (Java)
- Stores time-series features in InfluxDB
- Calls a Python FastAPI ML service (XGBoost + Isolation Forest) for predictions
- Applies a confidence gate C = 1-(σ/μ), threshold τ=0.75: DISPATCH or HOLD
- Spring Boot orchestrator receives predictions, pre-warms Redis, dispatches actions
- Everything visualized on Grafana dashboard

## TECH STACK
- Gateway: Go 1.22, net/http, golang-jwt/jwt/v5, redis/go-redis/v9, confluent-kafka-go/v2, prometheus/client_golang
- Streaming: Kafka Streams embedded in Java (NOT Flink — simpler, same resume value)
- Storage: InfluxDB 2.7 (time-series), Redis 7.x (cache+pubsub+ratelimit), PostgreSQL 16 (config+audit)
- ML Service: Python 3.11, FastAPI, uvicorn, xgboost, scikit-learn, pandas, numpy, pydantic
- Orchestrator: Java 21, Spring Boot 3.3, Spring Security, Spring Data JPA, Lettuce (Redis), InfluxDB client
- Infra: Docker Compose, Prometheus 2.51, Grafana 10.4, Kafka 7.6 (KRaft mode, no Zookeeper)

## NETWORKING (Docker internal DNS)
- gateway:8080
- kafka:9092
- redis:6379
- influxdb:8086
- postgres:5432
- ml-service:8000
- orchestrator:8090
- prometheus:9090
- grafana:3000

## ENVIRONMENT VARIABLES (from .env)
- JWT_SECRET=sentinel-super-secret-jwt-key-change-in-prod
- INFLUX_TOKEN=sentinel-influx-admin-token
- INFLUX_ORG=sentinel
- INFLUX_BUCKET=sentinel-metrics
- INFLUX_URL=http://influxdb:8086
- REDIS_ADDR=redis:6379
- KAFKA_BROKERS=kafka:9092
- RATE_LIMIT_PER_MIN=1000
- CONFIDENCE_THRESHOLD=0.75
- ML_SERVICE_URL=http://ml-service:8000
- POSTGRES_DSN=postgres://sentinel:sentinel123@postgres:5432/sentinel?sslmode=disable
- POSTGRES_USER=sentinel
- POSTGRES_PASSWORD=sentinel123
- POSTGRES_DB=sentinel

## KAFKA TOPICS
- api.events — raw request metadata (gateway publishes)
- api.features — computed 26-feature vectors (Kafka Streams publishes)
- scaling.actions — dispatch directives (orchestrator publishes, consumers act)

## KAFKA EVENT SCHEMA (api.events)
{"ts": 1700000000000, "endpoint": "/api/products", "method": "GET",
 "client_id": "user-abc", "latency_ms": 23, "status": 200, "bytes_sent": 1024}

## FEATURE VECTOR SCHEMA (26 features, exact order)
Temporal (8): hour_sin, hour_cos, dow_sin, dow_cos, week_of_year, is_weekend, is_holiday, day_of_month
Statistical (12): req_rate_1m, req_rate_5m, req_rate_15m, req_rate_30m,
                  latency_std_5m, latency_std_15m, req_max_5m, req_max_15m,
                  ewma_03, ewma_07, rate_of_change, autocorr_lag1
Infra State (6): cpu_util, memory_pressure, active_connections,
                 cache_hit_ratio, replica_count, queue_depth

## INFLUXDB SCHEMA
Measurement: api_features
Tags: endpoint (string)
Fields: all 26 feature names (float64)
Timestamp: nanosecond precision
Retention: 15 days

## CONFIDENCE GATE (from research paper)
C = 1 - (σ_pred / μ_pred)
where σ = std of prediction interval bounds, μ = predicted value
If C >= 0.75 → DISPATCH (pre-warm Redis, publish to scaling.actions)
If C < 0.75 → HOLD (log reason, do nothing)

## CURRENT STATUS
[UPDATE THIS AFTER EVERY SESSION]
Week: [1/2/3/4]
Current task: [what you are working on]
Completed:
- [ ] docker-compose.yml skeleton
- [ ] Go gateway: main.go
- [ ] Go gateway: JWT auth middleware
- [ ] Go gateway: rate limit middleware
- [ ] Go gateway: Kafka producer
- [ ] Go gateway: /metrics endpoint
- [ ] InfluxDB setup
- [ ] Kafka Streams feature job
- [ ] 26-feature vector pipeline
- [ ] Grafana basic dashboard
- [ ] Python ML: training data generator
- [ ] Python ML: XGBoost model trained
- [ ] Python ML: Isolation Forest trained
- [ ] Python ML: FastAPI service /predict /anomaly
- [ ] Spring Boot: PredictionScheduler
- [ ] Spring Boot: ConfidenceGate
- [ ] Spring Boot: ActionDispatcher
- [ ] Spring Boot: PostgreSQL audit log
- [ ] Full Grafana dashboard (7 panels)
- [ ] demo_surge.sh script
- [ ] README with architecture diagram

## KNOWN ISSUES / BLOCKERS
[Add any bugs or issues here so Opus has full context next session]