package com.sentinel.client;

import com.influxdb.client.InfluxDBClient;
import com.influxdb.client.InfluxDBClientFactory;
import com.influxdb.query.FluxRecord;
import com.influxdb.query.FluxTable;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

@Component
public class InfluxDBReader {
    private static final Logger logger = LoggerFactory.getLogger(InfluxDBReader.class);

    @Value("${influx.url:http://influxdb:8086}")
    private String url;

    @Value("${influx.token:sentinel-influx-admin-token}")
    private String token;

    @Value("${influx.org:sentinel}")
    private String org;

    @Value("${influx.bucket:sentinel-metrics}")
    private String bucket;

    private InfluxDBClient influxDBClient;

    @PostConstruct
    public void init() {
        this.influxDBClient = InfluxDBClientFactory.create(url, token.toCharArray(), org, bucket);
    }

    @PreDestroy
    public void close() {
        if (this.influxDBClient != null) {
            this.influxDBClient.close();
        }
    }

    public Optional<List<Double>> getLatestFeatureVector() {
        try {
            // Retrieves the most recent record aggregated over the last few seconds
            String query = String.format(
                "from(bucket: \"%s\") " +
                "|> range(start: -3m) " +
                "|> filter(fn: (r) => r[\"_measurement\"] == \"api_features\") " +
                "|> last() " + 
                "|> pivot(rowKey:[\"_time\"], columnKey: [\"_field\"], valueColumn: \"_value\")", bucket);
                
            List<FluxTable> tables = influxDBClient.getQueryApi().query(query);
            if (tables.isEmpty() || tables.get(0).getRecords().isEmpty()) {
                return Optional.empty();
            }

            FluxRecord record = tables.get(0).getRecords().get(0);
            
            // Map exact exact feature sequences needed for identical ML input constraints
            String[] featureNames = {
                "hour_sin", "hour_cos", "dow_sin", "dow_cos", "week_of_year", "is_weekend", "is_holiday", "day_of_month",
                "req_rate_1m", "req_rate_5m", "req_rate_15m", "req_rate_30m", "latency_std_5m", "latency_std_15m", "req_max_5m", "req_max_15m", "ewma_03", "ewma_07", "rate_of_change", "autocorr_lag1",
                "cpu_util", "memory_pressure", "active_connections", "cache_hit_ratio", "replica_count", "queue_depth"
            };
            
            List<Double> vector = new ArrayList<>();
            for (String field : featureNames) {
                Object val = record.getValueByKey(field);
                if (val == null) {
                    vector.add(0.0);
                } else if (val instanceof Number) {
                    vector.add(((Number) val).doubleValue());
                } else {
                    vector.add(0.0);
                }
            }
            if (vector.size() != 26) {
                return Optional.empty();
            }
            return Optional.of(vector);
        } catch (Exception e) {
            logger.error("Failed to read from InfluxDB: {}", e.getMessage());
            return Optional.empty();
        }
    }
}
