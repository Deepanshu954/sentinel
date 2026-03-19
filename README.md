# Sentinel

**Intelligent API Observability & Auto-Scaling Platform** — A 6-service distributed backend that predicts API traffic with ML, applies a confidence gate, and auto-scales infrastructure in real time.

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Deepanshu954/sentinel.git
cd sentinel

# 2. Create your environment file
cp .env.example .env

# 3. Launch all services
docker-compose up -d

# 4. Verify services are running
docker-compose ps
```

| Service       | URL                          |
|---------------|------------------------------|
| Gateway       | http://localhost:8080         |
| ML Service    | http://localhost:8000/docs    |
| Orchestrator  | http://localhost:8090         |
| Grafana       | http://localhost:3000         |
| Prometheus    | http://localhost:9090         |
| InfluxDB      | http://localhost:8086         |

---

## Architecture

<!-- TODO: Add architecture diagram -->

Sentinel is composed of six core services communicating over Kafka and Redis:

1. **Gateway (Go)** — JWT-authenticated API gateway with token-bucket rate limiting. Publishes request metadata to Kafka.
2. **Kafka (KRaft)** — Event backbone streaming raw events and computed feature vectors.
3. **Orchestrator (Spring Boot)** — Kafka Streams feature computation, confidence gate evaluation, and action dispatch.
4. **ML Service (Python/FastAPI)** — XGBoost prediction and Isolation Forest anomaly detection exposed via REST.
5. **InfluxDB** — Time-series storage for the 26-feature vectors with 15-day retention.
6. **Redis** — Cache pre-warming, pub/sub notifications, and sliding-window rate limiting.

Supporting infrastructure: PostgreSQL (config & audit), Prometheus (metrics scraping), Grafana (dashboards).

---

## Tech Stack

| Layer         | Technology                                                      |
|---------------|-----------------------------------------------------------------|
| Gateway       | Go 1.22, net/http, golang-jwt, go-redis, confluent-kafka-go    |
| Streaming     | Apache Kafka 7.6 (KRaft), Kafka Streams (Java 21)              |
| ML Service    | Python 3.11, FastAPI, XGBoost, scikit-learn, pandas             |
| Orchestrator  | Java 21, Spring Boot 3.3, Spring Data JPA, Lettuce              |
| Time-Series   | InfluxDB 2.7                                                    |
| Cache         | Redis 7.x                                                      |
| Database      | PostgreSQL 16                                                   |
| Observability | Prometheus 2.51, Grafana 10.4                                   |
| Infra         | Docker Compose                                                  |

---

## Project Structure

```
sentinel/
├── gateway/           # Go API gateway
├── ml-service/        # Python FastAPI ML service
├── orchestrator/      # Spring Boot orchestrator
├── infra/
│   ├── prometheus/    # Prometheus configuration
│   └── grafana/       # Grafana dashboards
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## License

MIT
