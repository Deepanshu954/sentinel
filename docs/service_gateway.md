# Service: Gateway (Go)

The Gateway is the entry point for all API traffic. It handles authentication, rate limiting, and event logging.

## Purpose
- **Authenticate**: Validates JWTs using HMAC-SHA256.
- **Rate Limit**: Implements a sliding-window rate limiter backed by Redis.
- **Produce**: Publishes every request's metadata to the `api.events` Kafka topic.

## WHERE is the code?
- **Entrypoint**: `gateway/main.go`
- **Middleware**: `gateway/middleware/` (Auth, RateLimit, Logging)
- **Kafka**: `gateway/kafka/producer.go`
- **Metrics**: `gateway/metrics/prometheus.go`

## Dependencies
- **Redis**: Stores rate-limiting counters.
  - **Key Pattern**: `ratelimit:{client_id}:{endpoint}`
  - **TTL**: 60 seconds (sliding window).
- **Kafka**: Receives `api.events` stream.
- **Prometheus**: Scrapes `/metrics` for traffic analysis.

## Metrics
The Gateway exposes the following key Prometheus metrics:
- `sentinel_gateway_requests_total`: Counter of all authenticated requests.
- `sentinel_gateway_request_duration_seconds`: Histogram of latency per endpoint.
- `sentinel_gateway_errors_total`: Counter of 4xx and 5xx responses.

## Safe/Dangerous Changes
- **[SAFE]**: Updating Prometheus labels or adding non-blocking logging.
- **[DANGEROUS]**: Modifying JWT validation logic or decreasing the rate limit without adjusting `.env`.

## Red Flags
- **401 Unauthorized**: Client credentials (JWT) are missing or invalid.
- **429 Too Many Requests**: Client has exceeded the configured rate limit.
- **502 Bad Gateway**: This is **expected** if no upstream backend is configured.
- **Kafka Connection Errors**: Logs will show "failed to produce message".
