# ── Build stage ───────────────────────────────────────────────────────────────
# Use Debian bookworm (glibc) — confluent-kafka-go bundles glibc-linked librdkafka
FROM golang:1.22-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libc6-dev librdkafka-dev pkg-config && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Cache dependency downloads
COPY go.mod go.sum ./
RUN go mod download

# Build the binary
COPY . .
RUN CGO_ENABLED=1 go build -ldflags="-s -w" -o sentinel-gateway .

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates librdkafka1 && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r sentinel && useradd -r -g sentinel sentinel

WORKDIR /app
COPY --from=builder /build/sentinel-gateway .

RUN chown sentinel:sentinel /app/sentinel-gateway

USER sentinel:sentinel

EXPOSE 8080

ENTRYPOINT ["/app/sentinel-gateway"]
