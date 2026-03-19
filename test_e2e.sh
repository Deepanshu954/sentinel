#!/bin/bash
set -e

# Run this script natively on your standard macOS terminal.
# It will rebuild the orchestrator, generate test traffic, and capture the E2E logs.

LOG_FILE="e2e_test_log.txt"
echo "=== SENTINEL E2E TEST LOG ===" > $LOG_FILE
date >> $LOG_FILE

echo -e "\n1. Rebuilding and Restarting Orchestrator Container..." | tee -a $LOG_FILE
docker compose up -d --build orchestrator >> $LOG_FILE 2>&1

echo -e "\nWaiting for Orchestrator to initialize..." | tee -a $LOG_FILE
sleep 15

echo -e "\n2. Generating JWT..." | tee -a $LOG_FILE
TOKEN=$(python3 scripts/generate_jwt.py | grep -Eo 'eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+' | head -n 1)
echo "Token generated." | tee -a $LOG_FILE

echo -e "\n3. Sending 20 requests to Gateway (/api/test)..." | tee -a $LOG_FILE
for i in {1..20}; do
  curl -s -o /dev/null -w "Response Code: %{http_code}\n" -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/test >> $LOG_FILE
  sleep 0.1
done

echo -e "\nWaiting for Kafka Streams and InfluxDBWriter to process..." | tee -a $LOG_FILE
sleep 5

echo -e "\n4. Checking InfluxDB for ingested feature vectors..." | tee -a $LOG_FILE
curl -s -k -H "Authorization: Token sentinel-influx-admin-token" \
  -H "Content-Type: application/vnd.flux" \
  -H "Accept: application/csv" \
  -d 'from(bucket:"sentinel-metrics") |> range(start: -10m) |> filter(fn: (r) => r._measurement == "api_features")' \
  "http://localhost:8086/api/v2/query?org=sentinel" >> $LOG_FILE

echo -e "\n5. Checking Orchestrator recent logs for Kafka Streams activity..." | tee -a $LOG_FILE
docker compose logs --tail=40 orchestrator >> $LOG_FILE

echo -e "\nDONE. Test results appended to $LOG_FILE."
