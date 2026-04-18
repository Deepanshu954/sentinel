# Sentinel Project Index

## Purpose
This file is a quick index of the repository to speed up onboarding, reviews, and issue triage.

## Top-Level Modules
- `gateway/`: Go API gateway (auth, rate limit, reverse proxy, Kafka publish, Prometheus metrics).
- `orchestrator/`: Spring Boot control plane (feature extraction, Influx read/write, ML call, gating, dispatch, audit persistence).
- `ml-service/`: FastAPI inference service + ML training/data-prep scripts.
- `demo-backend/`: local scaling target that degrades under heavy load.
- `scaling-sidecar/`: local actuator that applies replica changes through Docker Compose.
- `infra/`: Prometheus + Grafana provisioning and dashboards.
- `scripts/`: bootstrap, training, validation, demo, utility scripts.
- `docs/`: architecture, per-service docs, infra docs, research paper.

## Core Runtime Flow
1. `gateway/main.go` accepts `/api/*`, applies middleware, proxies, publishes `api.events`.
2. `orchestrator/.../FeatureExtractionJob.java` reads `api.events`, computes feature vectors, writes `api.features`.
3. `orchestrator/.../InfluxDBWriter.java` consumes `api.features`, writes to InfluxDB measurement `api_features`.
4. `orchestrator/.../PredictionScheduler.java` polls InfluxDB, calls ML `/predict`, applies confidence gate, dispatches or holds.
5. `orchestrator/.../ActionDispatcher.java` sends Redis pub/sub actions and increments metrics.
6. `orchestrator/.../ScalingActionRepository.java` stores decisions in PostgreSQL table `scaling_actions`.
7. `orchestrator/.../scaling/*` enforces policy and executes local scaling via sidecar.
8. `demo-backend` replica count changes provide real local autoscaling behavior.

## Key Files By Service

### Gateway (Go)
- `gateway/main.go`: bootstrapping, routes, middleware chain, proxy, kafka event publishing.
- `gateway/middleware/auth.go`: JWT validation and `client_id` context injection.
- `gateway/middleware/ratelimit.go`: Redis INCR/EXPIRE per-client limiter.
- `gateway/middleware/logging.go`: request logging + Prometheus counters/histograms.
- `gateway/kafka/producer.go`: async Kafka producer for `api.events`.
- `gateway/metrics/prometheus.go`: metric definitions.

### Orchestrator (Java)
- `orchestrator/src/main/resources/application.yml`: runtime config bindings.
- `orchestrator/src/main/java/com/sentinel/scheduler/PredictionScheduler.java`: periodic inference cycle.
- `orchestrator/src/main/java/com/sentinel/client/InfluxDBReader.java`: feature vector query/mapping.
- `orchestrator/src/main/java/com/sentinel/client/MLServiceClient.java`: REST client to ML service.
- `orchestrator/src/main/java/com/sentinel/gate/ConfidenceGate.java`: hold/dispatch gate logic.
- `orchestrator/src/main/java/com/sentinel/dispatcher/ActionDispatcher.java`: Redis dispatch + action metrics.
- `orchestrator/src/main/java/com/sentinel/scaling/ScalingExecutor.java`: scaling abstraction for local/AWS modes.
- `orchestrator/src/main/java/com/sentinel/scaling/ScalePolicy.java`: cooldown/hysteresis/min-max step guardrails.
- `orchestrator/src/main/java/com/sentinel/streaming/service/FeatureExtractionJob.java`: Kafka Streams feature extraction.
- `orchestrator/src/main/java/com/sentinel/streaming/service/InfluxDBWriter.java`: Kafka-to-Influx writer.
- `orchestrator/src/main/java/com/sentinel/model/ScalingAction.java`: JPA entity for audit trail.
- `orchestrator/src/main/java/com/sentinel/repository/ScalingActionRepository.java`: action query API.

### ML Service (Python)
- `ml-service/service/main.py`: FastAPI endpoints (`/predict`, `/anomaly`, `/health`, `/metrics`) and model load path.
- `ml-service/service/models.py`: pydantic schemas (currently separate from runtime path).
- `ml-service/ml/train_xgboost.py`: main + quantile bound model training.
- `ml-service/ml/train_isolation_forest.py`: anomaly model training.
- `ml-service/scripts/prepare_dataset.py`: dataset generation + feature engineering.
- `ml-service/scripts/generate_training_data.py`: synthetic high-volume data generator.
- `ml-service/scripts/build_multisource_training_data.py`: manifest-driven multi-source dataset fusion.
- `ml-service/scripts/dataset_manifest.json`: source registry and per-source processing controls.
- `ml-service/scripts/adapters/*`: dataset-specific parsers (`wikimedia`, `azure`, `google_cluster`, `alibaba`, `apache_access`).

### Infra / Tooling
- `docker-compose.yml`: full multi-service orchestration.
- `infra/prometheus/prometheus.yml`: scrape targets.
- `infra/grafana/provisioning/datasources/datasources.yml`: datasource provisioning.
- `infra/grafana/provisioning/dashboards/dashboards.yml`: dashboard provisioning.
- `scripts/validate_sentinel.sh`: 30-check validation suite.
- `scripts/demo.sh`: live load demo script.
- `scripts/train.sh`: local training orchestration.
- `scripts/fetch_public_datasets.sh`: fetches open NASA + Wikimedia datasets for local use.
- `scripts/build.sh`: local environment setup.

## Documentation Set
- `docs/0_overview.md`: system overview.
- `docs/service_gateway.md`: gateway behavior contract.
- `docs/service_orchestrator.md`: orchestrator expectations.
- `docs/service_ml.md`: ML service feature contract.
- `docs/infrastructure.md`: infra and observability map.
- `docs/API_Research_Paper.docx.pdf`: source paper being implemented.
- `docs/reports/`: remediation, dataset-upgrade, and local autoscaling execution reports.
- `docs/reports/FINAL_RELEASE_REPORT.md`: latest release-hardening verification snapshot.
