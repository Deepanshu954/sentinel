package com.sentinel.streaming.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.influxdb.client.InfluxDBClient;
import com.influxdb.client.InfluxDBClientFactory;
import com.influxdb.client.WriteApi;
import com.influxdb.client.WriteOptions;
import com.influxdb.client.domain.WritePrecision;
import com.influxdb.client.write.Point;
import com.sentinel.streaming.model.FeatureVector;

import jakarta.annotation.PreDestroy;

import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.common.serialization.StringDeserializer;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.List;
import java.util.Properties;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

@Service
public class InfluxDBWriter implements Runnable {

    private static final Logger log = LoggerFactory.getLogger(InfluxDBWriter.class);
    private static final String TOPIC = "api.features";
    private static final String GROUP_ID = "sentinel-influxdb-writer";

    @Value("${spring.kafka.bootstrap-servers:kafka:9092}")
    private String kafkaBrokers;

    @Value("${influx.url:http://influxdb:8086}")
    private String influxUrl;

    @Value("${influx.token:sentinel-influx-admin-token}")
    private String influxToken;

    @Value("${influx.org:sentinel}")
    private String org;

    @Value("${influx.bucket:sentinel-metrics}")
    private String bucket;

    private KafkaConsumer<String, String> consumer;
    private InfluxDBClient influxClient;
    private WriteApi writeApi;
    private final ObjectMapper mapper;
    private final AtomicBoolean running = new AtomicBoolean(true);
    private final ExecutorService executorService = Executors.newSingleThreadExecutor();

    public InfluxDBWriter(ObjectMapper mapper) {
        this.mapper = mapper;
        this.mapper.registerModule(new JavaTimeModule());
    }

    @EventListener(ApplicationReadyEvent.class)
    public void start() {
        this.influxClient = InfluxDBClientFactory.create(influxUrl, influxToken.toCharArray(), org, bucket);
        this.writeApi = influxClient.makeWriteApi(WriteOptions.builder()
                .batchSize(50)
                .flushInterval(2000)
                .bufferLimit(10_000)
                .jitterInterval(200)
                .retryInterval(2000)
                .maxRetries(3)
                .build());

        Properties props = new Properties();
        props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, kafkaBrokers);
        props.put(ConsumerConfig.GROUP_ID_CONFIG, GROUP_ID);
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "latest");
        props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, "true");

        this.consumer = new KafkaConsumer<>(props);
        this.consumer.subscribe(List.of(TOPIC));

        log.info("InfluxDBWriter initialized — consuming {} → InfluxDB {}/{}", TOPIC, org, bucket);
        executorService.submit(this);
    }

    @Override
    public void run() {
        try {
            while (running.get()) {
                ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(500));
                for (ConsumerRecord<String, String> record : records) {
                    try {
                        FeatureVector fv = mapper.readValue(record.value(), FeatureVector.class);
                        Point point = toInfluxPoint(fv);
                        if (writeApi != null) {
                            writeApi.writePoint(point);
                        }
                    } catch (Exception e) {
                        log.warn("Skipping malformed vector logic without crashing: {}", e.getMessage());
                    }
                }
            }
        } catch (Exception e) {
            if (running.get()) {
                log.error("InfluxDBWriter unexpected polling error: {}", e.getMessage(), e);
            }
        } finally {
            closeResources();
        }
    }

    private Point toInfluxPoint(FeatureVector fv) {
        return Point.measurement("api_features")
                .time(fv.timestamp(), WritePrecision.NS)
                .addTag("endpoint", fv.endpoint())
                .addField("hour_sin", fv.hourSin())
                .addField("hour_cos", fv.hourCos())
                .addField("dow_sin", fv.dowSin())
                .addField("dow_cos", fv.dowCos())
                .addField("week_of_year", fv.weekOfYear())
                .addField("is_weekend", fv.isWeekend())
                .addField("is_holiday", fv.isHoliday())
                .addField("day_of_month", fv.dayOfMonth())
                .addField("req_rate_1m", fv.reqRate1m())
                .addField("req_rate_5m", fv.reqRate5m())
                .addField("req_rate_15m", fv.reqRate15m())
                .addField("req_rate_30m", fv.reqRate30m())
                .addField("latency_std_5m", fv.latencyStd5m())
                .addField("latency_std_15m", fv.latencyStd15m())
                .addField("req_max_5m", fv.reqMax5m())
                .addField("req_max_15m", fv.reqMax15m())
                .addField("ewma_03", fv.ewma03())
                .addField("ewma_07", fv.ewma07())
                .addField("rate_of_change", fv.rateOfChange())
                .addField("autocorr_lag1", fv.autocorrLag1())
                .addField("cpu_util", fv.cpuUtil())
                .addField("memory_pressure", fv.memoryPressure())
                .addField("active_connections", fv.activeConnections())
                .addField("cache_hit_ratio", fv.cacheHitRatio())
                .addField("replica_count", fv.replicaCount())
                .addField("queue_depth", fv.queueDepth());
    }

    @PreDestroy
    public void stop() {
        running.set(false);
        executorService.shutdownNow();
    }

    private void closeResources() {
        log.info("InfluxDBWriter shutting down gracefully");
        try {
            if (writeApi != null) writeApi.close();
        } catch (Exception e) {}
        try {
            if (consumer != null) consumer.close();
        } catch (Exception e) {}
        try {
            if (influxClient != null) influxClient.close();
        } catch (Exception e) {}
    }
}
