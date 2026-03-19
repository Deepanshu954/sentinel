#!/bin/bash
mkdir -p target/tmp
echo "=== SENTINEL E2E TEST LOG ===" > e2e_test_log.txt
date >> e2e_test_log.txt

echo "Starting Orchestrator locally..." | tee -a e2e_test_log.txt
java -Djava.io.tmpdir=$(pwd)/target/tmp \
     -Dserver.port=8091 \
     -Dspring.kafka.bootstrap-servers=localhost:9092 \
     -Dinflux.url=http://localhost:8086 \
     -Dspring.datasource.url=jdbc:postgresql://localhost:5432/sentinel \
     -Dspring.datasource.username=sentinel \
     -Dspring.datasource.password=sentinel123 \
     -Dspring.data.redis.host=localhost \
     -jar target/orchestrator-1.0.0.jar > orchestrator.log 2>&1 &
PID=$!

echo "Waiting for Spring Boot to initialize..." | tee -a e2e_test_log.txt
sleep 15

echo "Generating JWT..." | tee -a e2e_test_log.txt
TOKEN=$(python3 ../scripts/generate_jwt.py | grep -Eo 'eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+' | head -n 1)

echo "Sending 20 test requests to Gateway..." | tee -a e2e_test_log.txt
for i in {1..20}; do
  curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/test >> e2e_test_log.txt
  sleep 0.1
done

echo "Waiting for Kafka Streams and InfluxDBWriter to process..." | tee -a e2e_test_log.txt
sleep 5

echo "Shutting down Orchestrator..." | tee -a e2e_test_log.txt
kill $PID

echo "Checking InfluxDB for saved Data..." | tee -a e2e_test_log.txt
curl -s -k -H "Authorization: Token sentinel-influx-admin-token" \
  -H "Content-Type: application/vnd.flux" \
  -H "Accept: application/csv" \
  -d 'from(bucket:"sentinel-metrics") |> range(start: -10m) |> filter(fn: (r) => r._measurement == "api_features")' \
  "http://localhost:8086/api/v2/query?org=sentinel" >> e2e_test_log.txt

echo "Appending Orchestrator logs (last 50 lines)..." | tee -a e2e_test_log.txt
tail -n 50 orchestrator.log >> e2e_test_log.txt

echo "DONE." | tee -a e2e_test_log.txt
