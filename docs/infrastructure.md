# Infrastructure & Monitoring

Sentinel relies on a robust set of supporting services for messaging, storage, and observability.

## Shared Infrastructure
- **Kafka (KRaft)**: `:9092`. Volume: `kafka_data`
- **Redis**: `:6379`. (No persistent volume)
- **InfluxDB**: `:8086`. Volume: `influxdb_data`
- **PostgreSQL**: `:5432`. Volume: `postgres_data`

## Monitoring & Dashboards
- **Prometheus**: Aggregates metrics from `gateway` and `ml-service`.
- **Grafana**: Visualizes overall system health across 7 curated panels.
  - **Port**: `:3000`
  - **Auth**: `admin` / `sentinel`

## Service-to-Service Mapping (Docker Network)

| Service | Container Name | Internal Port | External Port |
|---------|----------------|---------------|---------------|
| Gateway | sentinel-gateway | 8080 | 8080 |
| ML Service | sentinel-ml-service | 8000 | 8000 |
| Orchestrator | sentinel-orchestrator | 8080 | 8090 |
| InfluxDB | sentinel-influxdb | 8086 | 8086 |
| Prometheus | sentinel-prometheus | 9090 | 9090 |
| Grafana | sentinel-grafana | 3000 | 3000 |

## WHERE is the config?
- **Grafana Provisioning**: `infra/grafana/provisioning/`
- **Dashboards**: `infra/grafana/sentinel.json`
- **Prometheus Config**: `infra/prometheus/prometheus.yml`

## Red Flags
- **Kafka KRaft Initializing**: Kafka takes 30-60s to boot. If services are failing to connect, **WAIT**.
- **InfluxDB Bucket Missing**: The `sentinel-metrics` bucket must exist. Run `./scripts/fix_influx_bucket.sh` if validation check #17 fails.
- **Grafana Blank**: Check the datasource URL in `infra/grafana/provisioning/datasources/datasources.yml`.

## Quick Metrics Reference
- `sentinel_gateway_requests_total`: Total inbound request count.
- `sentinel_ml_prediction_latency_seconds`: Prediction model performance.
