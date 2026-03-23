# 🛡️ Sentinel

**Intelligent API Observability & Auto-Scaling Platform**

A distributed backend system that monitors API traffic in real-time, extracts 26 statistical features via streaming, and uses ML to predict load patterns and dispatch auto-scaling decisions.

```bash
bash launch.sh
```

---

## Architecture

```
                                    ┌─────────────────────────────────┐
                                    │           Grafana :3000         │
                                    │    (7-panel dashboard)          │
                                    └──────────┬──────────────────────┘
                                               │ query
                                    ┌──────────▼──────────────────────┐
                                    │        Prometheus :9090          │
                                    │    (scrapes all services)        │
                                    └──────────┬──────────────────────┘
                                               │ scrape
         ┌─────────────────────────────────────┐│
         │                                     ││
  HTTP   │  ┌──────────┐   ┌───────────┐  ┌───▼▼───────────────────┐
──────►  │  │  Redis    │   │  Kafka    │  │     Orchestrator       │
  :8080  │  │  :6379    │◄──┤  :9092    │◄─┤     :8090              │
         │  │(rate lim.)│   │           │  │  ┌─PredictionScheduler │
  ┌──────┤  └──────────┘   │ api.events│  │  ├─ConfidenceGate      │
  │  Go  │                 │ api.feats │  │  ├─ActionDispatcher     │
  │ Gate-│                 └─────┬─────┘  │  └─Kafka Streams       │
  │  way │                       │        │     (26 features)       │
  └──┬───┘                       │        └───────┬─────────────────┘
     │ publish                   │                │ REST
     └──────────────────────►    │                ▼
                                 │        ┌───────────────────────┐
                                 │        │    ML Service :8000   │
                                 │        │  ┌─XGBoost Regressor  │
              ┌──────────┐       │        │  └─Isolation Forest   │
              │PostgreSQL │◄─────┘        └───────────────────────┘
              │  :5432    │  audit log
              │(actions)  │       ┌───────────────────────┐
              └───────────┘       │    InfluxDB :8086      │
                                  │  (time-series store)   │
                                  └───────────────────────┘
```

## 🚀 Execution Order (How to run)

To properly start and test the Sentinel project from scratch, run the scripts in this exact order:

### 1. Build and Setup Environment
```bash
bash scripts/build.sh
```
**What it does:** Prepares your local host environment. It creates an isolated Python virtual environment (bypassing macOS SIP restrictions), installs strict ML pip dependencies, and compiles the Java Spring Boot orchestrator via Maven.

### 2. Train the Machine Learning Models
```bash
bash scripts/train.sh
```
**What it does:** Downloads and prepares the Azure/Wikipedia telemetry datasets, scales the features, and trains the XGBoost Regressor (for traffic prediction) and the Isolation Forest (for anomaly detection). The trained models are saved into `ml-service/model_weights/`.

### 3. Deploy the Platform
```bash
bash launch.sh
```
**What it does:** The master orchestration script. It loads environment variables, spins up all 9 services concurrently via Docker Compose, and features a robust retry loop that waits until every single container (from Kafka KRaft to the Python Uvicorn server) reports a `200 OK` health status.

### 4. Validate the Architecture
```bash
bash scripts/validate_sentinel.sh
```
**What it does:** Executes a rigorous 30-point automated test suite. It generates JWT tokens, tests Redis rate-limiting (HTTP 429), traces feature vectors through the Kafka pub/sub queue, verifies InfluxDB batch writes, and confirms Prometheus actually scrapes the dynamically registered components. (Aim for 30/30!).

### 5. Run the Interactive Live Demo
```bash
bash scripts/demo.sh
```
**What it does:** An interactive CLI load-testing dashboard. It floods the gateway with live synthetic traffic using `hey` in three phases (Baseline, Surge, Recovery) and live-prints the Orchestrator's AI-driven scaling actions (e.g., `SCALE_OUT`, `HOLD`) and anomaly detections directly to your terminal.

---

## Commands

### sentinel.sh (recommended)
```bash
./sentinel.sh start      # Full launch with health checks
./sentinel.sh stop       # Stop all services
./sentinel.sh restart    # Restart all services
./sentinel.sh status     # Show running services
./sentinel.sh test       # Run 30-point validation
./sentinel.sh demo       # Run live demo
./sentinel.sh logs       # Tail orchestrator logs
./sentinel.sh token      # Generate JWT token
./sentinel.sh curl       # Fire an authenticated test request
./sentinel.sh build ml-service  # Rebuild a specific service
./sentinel.sh clean      # Delete all data & volumes
```

### Make targets
```bash
make up      # Start all services
make down    # Stop all services
make test    # Run validation suite
make demo    # Run live demo
make train   # Train ML models in container
make clean   # Destroy all data
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **API Gateway** | Go 1.22 | JWT auth, rate limiting, Kafka publishing |
| **Message Broker** | Apache Kafka (KRaft) | Event streaming, no Zookeeper |
| **Stream Processing** | Kafka Streams (Java) | 26-feature extraction pipeline |
| **Orchestrator** | Spring Boot 3.3 | ML integration, confidence gate, action dispatch |
| **ML Service** | Python FastAPI | XGBoost prediction, Isolation Forest anomaly detection |
| **Time-Series DB** | InfluxDB 2.7 | Feature vector storage |
| **Cache** | Redis 7 | Rate limiting, action dispatch |
| **Relational DB** | PostgreSQL 16 | Scaling action audit log |
| **Monitoring** | Prometheus + Grafana | Metrics collection, dashboards |

## Services & Ports

| Service | Port | URL |
|---------|------|-----|
| API Gateway | 8080 | http://localhost:8080 |
| ML Service | 8000 | http://localhost:8000 |
| Orchestrator | 8090 | http://localhost:8090 |
| Grafana | 3000 | http://localhost:3000 |
| Prometheus | 9090 | http://localhost:9090 |
| InfluxDB | 8086 | http://localhost:8086 |
| Kafka | 9092 | — |
| Redis | 6379 | — |
| PostgreSQL | 5432 | — |

**Grafana login:** `admin` / `sentinel`

---

## Project Structure

```
sentinel/
├── gateway/                    # Go API gateway
│   ├── main.go                 # HTTP server, routing
│   ├── middleware/
│   │   ├── auth.go             # JWT authentication
│   │   ├── ratelimit.go        # Redis-backed rate limiting
│   │   └── logging.go          # Request logging
│   ├── kafka/producer.go       # Kafka event publisher
│   ├── metrics/prometheus.go   # Prometheus metrics
│   └── Dockerfile
├── orchestrator/               # Spring Boot orchestrator
│   └── src/main/java/com/sentinel/
│       ├── client/             # MLServiceClient, InfluxDBReader
│       ├── gate/               # ConfidenceGate
│       ├── dispatcher/         # ActionDispatcher
│       ├── scheduler/          # PredictionScheduler
│       └── stream/             # Kafka Streams topology
├── ml-service/                 # Python ML service
│   ├── main.py                 # FastAPI entrypoint
│   ├── service/main.py         # API routes (/predict, /anomaly)
│   ├── ml/                     # Training scripts
│   ├── models/                 # Trained model artifacts (.json, .pkl)
│   └── scripts/                # Data generation script
├── infra/
│   ├── grafana/                # Dashboard + datasource configs
│   └── prometheus/             # Prometheus scrape config
├── scripts/
│   ├── build.sh                # Compiles Java code and sets up Python environment
│   ├── train.sh                # Downloads data and trains XGBoost/Isolation Forest models
│   ├── validate_sentinel.sh    # 30-point pipeline validation suite
│   ├── demo.sh                 # Live traffic simulation dashboard
│   ├── prepare_dataset.py      # Cleans Azure/Wiki datasets bounds
│   └── generate_jwt.py         # JWT token generator for auth
├── docker-compose.yml          # 9-service stack
├── launch.sh                   # Master Docker deployment script
├── sentinel.sh                 # CLI utility
├── Makefile                    # Make targets
├── DOCS.md                     # Complete developer docs
└── README.md
```

## Validation

```bash
bash scripts/validate_sentinel.sh
```

Runs 30 checks across all components:
- **Week 0**: Docker infrastructure (9 services)
- **Week 1**: Gateway, JWT, rate limiting, Kafka events
- **Week 2**: Orchestrator, Kafka Streams, InfluxDB feature ingestion
- **Week 3**: ML service, prediction, anomaly detection
- **Week 4**: Prometheus, Grafana, dashboards

## License

MIT

**Developer:** Deepanshu Chauhan (E23CSEU1617, Bennett University)
**Research Paper:** Optimizing API Performance Using AI-Based Predictive Request Management
