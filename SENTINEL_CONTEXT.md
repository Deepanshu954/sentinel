# SENTINEL — Master Context File
# Update this file after every session. Drag into Antigravity at the start of every session.

## PROJECT IDENTITY
Name: Sentinel — Intelligent API Observability & Auto-Scaling Platform
GitHub: https://github.com/Deepanshu954/sentinel
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
- Streaming: Kafka Streams embedded in Java
- Storage: InfluxDB 2.7, Redis 7.x, PostgreSQL 16
- ML Service: Python 3.11, FastAPI, xgboost, scikit-learn
- Orchestrator: Java 21, Spring Boot 3.3
- Infra: Docker Compose, Prometheus, Grafana, Kafka (KRaft mode)

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
- api.events — raw request metadata (gateway publishes) ✅
- api.features — feature vectors (Kafka Streams publishes) ✅
- scaling.actions — dispatch directives (future)

## KAFKA EVENT SCHEMA (api.events)
{"ts":1700000000000,"endpoint":"/api/products","method":"GET","client_id":"user-abc","latency_ms":23,"status":200,"bytes_sent":1024}

## FEATURE VECTOR SCHEMA (TARGET - 26 features)
Temporal (8): hour_sin, hour_cos, dow_sin, dow_cos, week_of_year, is_weekend, is_holiday, day_of_month  
Statistical (12): req_rate_1m, req_rate_5m, req_rate_15m, req_rate_30m,
latency_std_5m, latency_std_15m, req_max_5m, req_max_15m,
ewma_03, ewma_07, rate_of_change, autocorr_lag1  
Infra State (6): cpu_util, memory_pressure, active_connections,
cache_hit_ratio, replica_count, queue_depth  

## CURRENT FEATURE PIPELINE (IMPLEMENTED)
Currently only minimal features are implemented:
- request_count
- latency_avg
- req_rate_1m

Example:
{
  "endpoint": "/api/test",
  "timestamp": "...",
  "request_count": 1,
  "latency_avg": 3.0,
  "req_rate_1m": 1.0
}

## INFLUXDB SCHEMA
Measurement: api_features  
Tags: endpoint (string)  
Fields: all 26 feature names (float64)  
Timestamp: nanosecond precision  
Retention: 15 days  

## CONFIDENCE GATE (from research paper)
C = 1 - (σ_pred / μ_pred)
If C >= 0.75 → DISPATCH  
If C < 0.75 → HOLD  

## CURRENT STATUS
Week: 2 COMPLETED ✅  
Current task: Week 2.2 — InfluxDB + Grafana integration  

Completed:
- [x] docker-compose.yml skeleton
- [x] Go gateway: main.go
- [x] Go gateway: JWT auth middleware
- [x] Go gateway: rate limit middleware
- [x] Go gateway: Kafka producer
- [x] Go gateway: /metrics endpoint
- [x] InfluxDB setup (via docker-compose)
- [x] scripts/generate_jwt.py for testing

- [x] Kafka Streams feature job (basic version implemented)
- [ ] 26-feature vector pipeline (only 3 features implemented currently)
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
- [x] README with architecture diagram

## KNOWN ISSUES / BLOCKERS
- Feature pipeline is minimal (only 3 features)
- No rolling window aggregation yet
- InfluxDB ingestion not fully verified
- Grafana dashboard not configured

## SYSTEM STATE SUMMARY

Gateway → Kafka → Streams → Features  
✅ WORKING END-TO-END  

Next:
Features → InfluxDB → Grafana  
🚧 IN PROGRESS