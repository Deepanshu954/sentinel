# Service: Orchestrator (Java/Spring Boot)

The Orchestrator is the brain of the platform. It extracts features from raw traffic events and coordinates scaling decisions.

## Purpose
- **Feature Extraction**: Runs a Kafka Streams topology that computes 26 rolling features (1m, 5m, 15m windows).
- **Inference Coordinator**: Polls InfluxDB every 5 seconds for the latest feature vector and calls the ML Service.
- **Confidence Gate**: Evaluates prediction certainty (C ≥ 0.75). If uncertain, it holds the action.
- **Action Dispatcher**: Publishes scaling directives to Redis and logs them to PostgreSQL.

## WHERE is the code?
- **Kafka Streams**: `orchestrator/src/main/java/com/sentinel/streaming/`
- **ML Client**: `orchestrator/src/main/java/com/sentinel/client/MLServiceClient.java`
- **Confidence Gate**: `orchestrator/src/main/java/com/sentinel/gate/ConfidenceGate.java`
- **Audit Log**: `orchestrator/src/main/java/com/sentinel/dispatcher/ActionDispatcher.java`

## Dependencies
- **Kafka**: Consumes `api.events`, produces `api.features`.
  - **Windowing**: 1-minute, 5-minute, 15-minute, and 30-minute rolling windows.
- **InfluxDB**: Storage for all 26 computed features.
- **ML Service**: Provides prediction and anomaly endpoints.
- **PostgreSQL**: Hardened audit trail for all scaling actions.
  - **Table Schema**: `scaling_actions`
    - `id`: Serial Primary Key
    - `endpoint`: VARCHAR(255)
    - `predicted_rate`: FLOAT
    - `confidence`: FLOAT
    - `action`: VARCHAR(50) (DISPATCH/HOLD)
    - `created_at`: TIMESTAMP DEFAULT NOW()

## Safe/Dangerous Changes
- **[SAFE]**: Adjusting the `CONFIDENCE_THRESHOLD` in `.env`.
- **[DANGEROUS]**: Changing the feature extraction order (it MUST match the ML model's expected 26-feature input array).

## Red Flags
- **"InfluxDB Query returned empty"**: Gateway is likely not producing events, or Kafka Streams is stalled.
- **"Prediction too uncertain"**: ML model is struggling with high variance traffic (Holding state).
- **PostgreSQL Connection Failures**: Check `POSTGRES_USER` role permissions.
