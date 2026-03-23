package com.sentinel.streaming.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.sentinel.streaming.model.FeatureVector;
import jakarta.annotation.PreDestroy;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.processor.api.Processor;
import org.apache.kafka.streams.processor.api.ProcessorContext;
import org.apache.kafka.streams.processor.api.Record;
import org.apache.kafka.streams.state.KeyValueStore;
import org.apache.kafka.streams.state.StoreBuilder;
import org.apache.kafka.streams.state.Stores;
import org.apache.kafka.streams.state.WindowStore;
import org.apache.kafka.streams.state.WindowStoreIterator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.temporal.IsoFields;
import java.util.ArrayList;
import java.util.List;
import java.util.Properties;

@Service
public class FeatureExtractionJob {

    private static final Logger log = LoggerFactory.getLogger(FeatureExtractionJob.class);

    private final ObjectMapper mapper;
    private final Properties kafkaStreamsProperties;
    private KafkaStreams streams;

    public FeatureExtractionJob(ObjectMapper mapper, @Qualifier("kafkaStreamsProperties") Properties kafkaStreamsProperties) {
        this.mapper = mapper;
        this.mapper.registerModule(new JavaTimeModule());
        this.kafkaStreamsProperties = kafkaStreamsProperties;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void start() {
        Topology topology = new Topology();

        StoreBuilder<WindowStore<String, Long>> countStoreBuilder = Stores.windowStoreBuilder(
                Stores.persistentWindowStore("count-window", Duration.ofMinutes(30), Duration.ofSeconds(1), false),
                Serdes.String(),
                Serdes.Long()
        );
        StoreBuilder<WindowStore<String, Double>> latencyStoreBuilder = Stores.windowStoreBuilder(
                Stores.persistentWindowStore("latency-window", Duration.ofMinutes(15), Duration.ofSeconds(1), false),
                Serdes.String(),
                Serdes.Double()
        );

        StoreBuilder<KeyValueStore<String, String>> keyValueStoreBuilder = Stores.keyValueStoreBuilder(
                Stores.persistentKeyValueStore("ewma-store"),
                Serdes.String(),
                Serdes.String()
        );

        topology.addSource("Source", "api.events")
                .addProcessor("Process", () -> new FeatureProcessor(mapper), "Source")
                .addStateStore(countStoreBuilder, "Process")
                .addStateStore(latencyStoreBuilder, "Process")
                .addStateStore(keyValueStoreBuilder, "Process")
                .addSink("Sink", "api.features", "Process");

        streams = new KafkaStreams(topology, kafkaStreamsProperties);

        streams.setUncaughtExceptionHandler(e -> {
            log.error("Kafka Streams Uncaught Exception", e);
            return org.apache.kafka.streams.errors.StreamsUncaughtExceptionHandler.StreamThreadExceptionResponse.REPLACE_THREAD;
        });

        streams.start();
        log.info("Kafka Streams FeatureExtractionJob 26-Feature Pipeline Started.");
    }

    @PreDestroy
    public void stop() {
        if (streams != null) {
            streams.close();
        }
    }

    public static class FeatureProcessor implements Processor<String, String, String, String> {
        private final ObjectMapper mapper;
        private ProcessorContext<String, String> context;
        private WindowStore<String, Long> countStore;
        private WindowStore<String, Double> latencyStore;
        private KeyValueStore<String, String> ewmaStore;

        public FeatureProcessor(ObjectMapper mapper) {
            this.mapper = mapper;
        }

        @Override
        public void init(ProcessorContext<String, String> context) {
            this.context = context;
            this.countStore = context.getStateStore("count-window");
            this.latencyStore = context.getStateStore("latency-window");
            this.ewmaStore = context.getStateStore("ewma-store");
        }

        @Override
        public void process(Record<String, String> record) {
            try {
                JsonNode node = mapper.readTree(record.value());
                String endpoint = node.has("endpoint") ? node.get("endpoint").asText() : "unknown";
                
                long timestamp;
                if (node.has("timestamp") && node.get("timestamp").isTextual()) {
                    timestamp = Instant.parse(node.get("timestamp").asText()).toEpochMilli();
                } else if (node.has("ts")) {
                    timestamp = node.get("ts").asLong();
                } else {
                    timestamp = record.timestamp();
                }

                Double latency = node.has("latency_avg") ? node.get("latency_avg").asDouble() : (node.has("latency") ? node.get("latency").asDouble() : 10.0);

                long windowStart = (timestamp / 1000) * 1000;
                
                long currentCount = 0L;
                try (WindowStoreIterator<Long> iter = countStore.fetch(endpoint, windowStart, windowStart)) {
                    if (iter.hasNext()) currentCount = iter.next().value;
                }
                countStore.put(endpoint, currentCount + 1, windowStart);
                latencyStore.put(endpoint, latency, windowStart);

                EndpointPersistentState persistentState;
                String stateStr = ewmaStore.get(endpoint);
                if (stateStr == null) {
                    persistentState = new EndpointPersistentState();
                } else {
                    persistentState = mapper.readValue(stateStr, EndpointPersistentState.class);
                }

                Instant eventTime = Instant.ofEpochMilli(timestamp);
                LocalDateTime ldt = LocalDateTime.ofInstant(eventTime, ZoneOffset.UTC);

                int hour = ldt.getHour();
                int dayOfWeek = ldt.getDayOfWeek().getValue();
                double hourSin = Math.sin(2 * Math.PI * hour / 24.0);
                double hourCos = Math.cos(2 * Math.PI * hour / 24.0);
                double dowSin = Math.sin(2 * Math.PI * dayOfWeek / 7.0);
                double dowCos = Math.cos(2 * Math.PI * dayOfWeek / 7.0);
                double weekOfYear = ldt.get(IsoFields.WEEK_OF_WEEK_BASED_YEAR);
                double isWeekend = (dayOfWeek >= 6) ? 1.0 : 0.0;
                double isHoliday = 0.0;
                double dayOfMonth = ldt.getDayOfMonth();

                Runtime rt = Runtime.getRuntime();
                long maxMemory = rt.maxMemory();
                long memoryUsed = rt.totalMemory() - rt.freeMemory();
                double memoryPressure = maxMemory > 0 ? (double) memoryUsed / maxMemory : 0.0;
                double cpuUtil = memoryPressure; 
                double activeConnections = 1.0;
                double cacheHitRatio = 0.5;
                double replicaCount = 1.0;
                double queueDepth = 0.0;

                long t1m = timestamp - 60000;
                long t5m = timestamp - 300000;
                long t15m = timestamp - 900000;
                long t30m = timestamp - 1800000;

                long total1m = 0, total5m = 0, total15m = 0, total30m = 0;
                long reqMax5m = 0, reqMax15m = 0;

                try (WindowStoreIterator<Long> iter = countStore.fetch(endpoint, t30m, timestamp)) {
                    while (iter.hasNext()) {
                        org.apache.kafka.streams.KeyValue<Long, Long> entry = iter.next();
                        long ts = entry.key;
                        long val = entry.value;
                        total30m += val;
                        
                        if (ts >= t15m) {
                            total15m += val;
                            reqMax15m = Math.max(reqMax15m, val);
                        }
                        if (ts >= t5m) {
                            total5m += val;
                            reqMax5m = Math.max(reqMax5m, val);
                        }
                        if (ts >= t1m) {
                            total1m += val;
                        }
                    }
                }

                double reqRate1m = total1m / 60.0;
                double reqRate5m = total5m / 300.0;
                double reqRate15m = total15m / 900.0;
                double reqRate30m = total30m / 1800.0;

                List<Double> latencies5m = new ArrayList<>();
                List<Double> latencies15m = new ArrayList<>();
                try (WindowStoreIterator<Double> iter = latencyStore.fetch(endpoint, t15m, timestamp)) {
                    while (iter.hasNext()) {
                        org.apache.kafka.streams.KeyValue<Long, Double> entry = iter.next();
                        long ts = entry.key;
                        double val = entry.value;
                        latencies15m.add(val);
                        if (ts >= t5m) {
                            latencies5m.add(val);
                        }
                    }
                }

                double latencyStd5m = calcStdDev(latencies5m);
                double latencyStd15m = calcStdDev(latencies15m);

                double ewma03 = persistentState.ewma03;
                double ewma07 = persistentState.ewma07;
                
                if (Double.isNaN(ewma03)) {
                    ewma03 = reqRate1m;
                    ewma07 = reqRate1m;
                } else {
                    ewma03 = 0.3 * reqRate1m + 0.7 * ewma03;
                    ewma07 = 0.7 * reqRate1m + 0.3 * ewma07;
                }
                persistentState.ewma03 = ewma03;
                persistentState.ewma07 = ewma07;

                double maxPrev = Math.max(persistentState.prevReqRate1m, 1.0);
                double rateOfChange = (reqRate1m - persistentState.prevReqRate1m) / maxPrev;
                persistentState.prevReqRate1m = reqRate1m;

                persistentState.history.add(reqRate1m);
                if (persistentState.history.size() > 60) {
                    persistentState.history.remove(0);
                }
                double autocorrLag1 = calcAutocorr(persistentState.history);

                ewmaStore.put(endpoint, mapper.writeValueAsString(persistentState));

                FeatureVector fv = new FeatureVector(
                        endpoint, eventTime,
                        hourSin, hourCos, dowSin, dowCos, weekOfYear, isWeekend, isHoliday, dayOfMonth,
                        reqRate1m, reqRate5m, reqRate15m, reqRate30m,
                        latencyStd5m, latencyStd15m, reqMax5m, reqMax15m,
                        ewma03, ewma07, rateOfChange, autocorrLag1,
                        cpuUtil, memoryPressure, activeConnections, cacheHitRatio, replicaCount, queueDepth
                );

                context.forward(new Record<>(endpoint, mapper.writeValueAsString(fv), eventTime.toEpochMilli()));

            } catch (Exception e) {
                log.warn("Invalid event JSON safely ignored: {}", e.getMessage());
            }
        }

        private double calcStdDev(List<Double> values) {
            if (values.size() < 2) return 0.0;
            double mean = values.stream().mapToDouble(v -> v).average().orElse(0.0);
            double sumSq = values.stream().mapToDouble(v -> Math.pow(v - mean, 2)).sum();
            return Math.sqrt(sumSq / (values.size() - 1));
        }

        private double calcAutocorr(List<Double> history) {
            if (history.size() < 3) return 0.0;
            int n = history.size();
            double sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;
            for (int i = 0; i < n - 1; i++) {
                double x = history.get(i + 1);
                double y = history.get(i);
                sumX += x;
                sumY += y;
                sumXY += x * y;
                sumX2 += x * x;
                sumY2 += y * y;
            }
            int count = n - 1;
            double denominator = Math.sqrt((count * sumX2 - sumX * sumX) * (count * sumY2 - sumY * sumY));
            if (denominator == 0) return 0.0;
            return (count * sumXY - sumX * sumY) / denominator;
        }

        static class EndpointPersistentState {
            public double ewma03 = Double.NaN;
            public double ewma07 = Double.NaN;
            public double prevReqRate1m = 0.0;
            public List<Double> history = new ArrayList<>();
        }
    }
}
