#!/bin/bash
set -e

echo "Building standalone orchestrator Docker image..."
docker build -t sentinel-orchestrator-test ./orchestrator > /dev/null

echo "Removing old container if exists..."
docker rm -f sentinel-orchestrator || true

echo "Starting orchestrator in sentinel-network..."
docker run -d --name sentinel-orchestrator \
  --network sentinel_sentinel-network \
  -e SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/sentinel \
  -e SPRING_DATASOURCE_USERNAME=sentinel \
  -e SPRING_DATASOURCE_PASSWORD=sentinel123 \
  -e REDIS_ADDR=redis:6379 \
  -e KAFKA_BROKERS=kafka:9092 \
  -e INFLUX_URL=http://influxdb:8086 \
  -e INFLUX_TOKEN=sentinel-influx-admin-token \
  -e INFLUX_ORG=sentinel \
  -e INFLUX_BUCKET=sentinel-metrics \
  sentinel-orchestrator-test

echo "Waiting for Spring Boot to start..."
sleep 15

LOG_FILE="e2e_test_log.txt"
echo "=== SENTINEL E2E TEST LOG ===" > $LOG_FILE
date >> $LOG_FILE

echo -e "\n1. Generating JWT..." | tee -a $LOG_FILE
TOKEN=$(python3 scripts/generate_jwt.py | grep -Eo 'eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+' | head -n 1)

echo -e "\n2. Sending 20 requests to Gateway (/api/test)..." | tee -a $LOG_FILE
for i in {1..20}; do
  curl -s -o /dev/null -w "Response Code: %{http_code}\n" -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/test >> $LOG_FILE
  sleep 0.1
done

echo -e "\nWaiting for Kafka Streams and InfluxDBWriter to process..." | tee -a $LOG_FILE
sleep 5

echo -e "\n3. Checking InfluxDB for ingested feature vectors..." | tee -a $LOG_FILE
curl -s -k -H "Authorization: Token sentinel-influx-admin-token" \
  -H "Content-Type: application/vnd.flux" \
  -H "Accept: application/csv" \
  -d 'from(bucket:"sentinel-metrics") |> range(start: -10m) |> filter(fn: (r) => r._measurement == "api_features")' \
  "http://localhost:8086/api/v2/query?org=sentinel" >> $LOG_FILE

echo -e "\n4. Checking Orchestrator recent logs for Kafka Streams activity..." | tee -a $LOG_FILE
docker logs --tail=40 sentinel-orchestrator >> $LOG_FILE

echo "DONE. Check e2e_test_log.txt"
