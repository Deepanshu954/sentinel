package com.sentinel.streaming.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.sentinel.streaming.model.FeatureVector;
import jakarta.annotation.PreDestroy;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.Topology;
import org.apache.kafka.streams.processor.PunctuationType;
import org.apache.kafka.streams.processor.api.Processor;
import org.apache.kafka.streams.processor.api.ProcessorContext;
import org.apache.kafka.streams.processor.api.Record;
import org.apache.kafka.streams.state.KeyValueIterator;
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
import java.util.*;

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

        StoreBuilder<WindowStore<String, String>> windowStoreBuilder = Stores.windowStoreBuilder(
                Stores.persistentWindowStore(
                        "event-window-store",
                        Duration.ofMinutes(30),
                        Duration.ofMinutes(30),
                        false
                ),
                Serdes.String(),
                Serdes.String()
        );

        StoreBuilder<KeyValueStore<String, String>> keyValueStoreBuilder = Stores.keyValueStoreBuilder(
                Stores.persistentKeyValueStore("ewma-store"),
                Serdes.String(),
                Serdes.String()
        );

        topology.addSource("Source", "api.events")
                .addProcessor("Process", () -> new FeatureProcessor(mapper), "Source")
                .addStateStore(windowStoreBuilder, "Process")
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
        private WindowStore<String, String> windowStore;
        private KeyValueStore<String, String> ewmaStore;

        public FeatureProcessor(ObjectMapper mapper) {
            this.mapper = mapper;
        }

        @Override
        public void init(ProcessorContext<String, String> context) {
            this.context = context;
            this.windowStore = context.getStateStore("event-window-store");
            this.ewmaStore = context.getStateStore("ewma-store");

            context.schedule(Duration.ofSeconds(1), PunctuationType.WALL_CLOCK_TIME, this::punctuate);
        }

        @Override
        public void process(Record<String, String> record) {
            try {
                JsonNode node = mapper.readTree(record.value());
                String endpoint = node.has("endpoint") ? node.get("endpoint").asText() : "unknown";
                long timestamp = node.has("ts") ? node.get("ts").asLong() : record.timestamp();

                // Store event keyed by endpoint
                windowStore.put(endpoint, record.value(), timestamp);
                
                // Keep the EWMA state initialized
                if (ewmaStore.get(endpoint) == null) {
                    EndpointPersistentState state = new EndpointPersistentState();
                    ewmaStore.put(endpoint, mapper.writeValueAsString(state));
                }

            } catch (Exception e) {
                log.warn("Invalid event JSON safely ignored: {}", e.getMessage());
            }
        }

        private void punctuate(long timestamp) {
            Instant now = Instant.now();
            LocalDateTime ldt = LocalDateTime.ofInstant(now, ZoneOffset.UTC);

            // Compute temporal
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

            // Infra (MVP)
            Runtime rt = Runtime.getRuntime();
            long maxMemory = rt.maxMemory();
            long memoryUsed = rt.totalMemory() - rt.freeMemory();
            double memoryPressure = maxMemory > 0 ? (double) memoryUsed / maxMemory : 0.0;
            double cpuUtil = memoryPressure; // pseudo logic, oshi is normally needed but simplified for MVP without pulling deps heavily
            double activeConnections = 1.0;
            double cacheHitRatio = 0.5;
            double replicaCount = 1.0;
            double queueDepth = 0.0;

            // Compute statistical per endpoint
            try (KeyValueIterator<String, String> endpoints = ewmaStore.all()) {
                while (endpoints.hasNext()) {
                    org.apache.kafka.streams.KeyValue<String, String> entry = endpoints.next();
                    String endpoint = entry.key;

                    EndpointPersistentState persistentState = mapper.readValue(entry.value, EndpointPersistentState.class);

                    long t1m = now.minusSeconds(60).toEpochMilli();
                    long t5m = now.minusSeconds(300).toEpochMilli();
                    long t15m = now.minusSeconds(900).toEpochMilli();
                    long t30m = now.minusSeconds(1800).toEpochMilli();

                    List<Long> latencies1m = new ArrayList<>();
                    List<Long> latencies5m = new ArrayList<>();
                    List<Long> latencies15m = new ArrayList<>();
                    List<Long> requestCounts1mWindow = new ArrayList<>();
                    List<Long> requestCounts5mWindow = new ArrayList<>();
                    List<Long> requestCounts15mWindow = new ArrayList<>();
                    List<Long> requestCounts30mWindow = new ArrayList<>();

                    long epochNow = now.toEpochMilli();
                    try (WindowStoreIterator<String> iterator = windowStore.fetch(endpoint, t30m, epochNow)) {
                        while (iterator.hasNext()) {
                            org.apache.kafka.streams.KeyValue<Long, String> windowEntry = iterator.next();
                            long ts = windowEntry.key;
                            try {
                                JsonNode node = mapper.readTree(windowEntry.value);
                                long latency = node.has("latency_ms") ? node.get("latency_ms").asLong() : 0;
                                
                                requestCounts30mWindow.add(ts);
                                if (ts >= t15m) {
                                    requestCounts15mWindow.add(ts);
                                    latencies15m.add(latency);
                                }
                                if (ts >= t5m) {
                                    requestCounts5mWindow.add(ts);
                                    latencies5m.add(latency);
                                }
                                if (ts >= t1m) {
                                    requestCounts1mWindow.add(ts);
                                    latencies1m.add(latency);
                                }
                            } catch (Exception ignored) {}
                        }
                    }

                    double reqRate1m = requestCounts1mWindow.size() / 60.0;
                    double reqRate5m = requestCounts5mWindow.size() / 300.0;
                    double reqRate15m = requestCounts15mWindow.size() / 900.0;
                    double reqRate30m = requestCounts30mWindow.size() / 1800.0;

                    double latencyStd5m = calcStdDev(latencies5m);
                    double latencyStd15m = calcStdDev(latencies15m);
                    
                    double reqMax5m = requestCounts5mWindow.size(); 
                    double reqMax15m = requestCounts15mWindow.size();

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
                            endpoint, now,
                            hourSin, hourCos, dowSin, dowCos, weekOfYear, isWeekend, isHoliday, dayOfMonth,
                            reqRate1m, reqRate5m, reqRate15m, reqRate30m,
                            latencyStd5m, latencyStd15m, reqMax5m, reqMax15m,
                            ewma03, ewma07, rateOfChange, autocorrLag1,
                            cpuUtil, memoryPressure, activeConnections, cacheHitRatio, replicaCount, queueDepth
                    );

                    context.forward(new Record<>(endpoint, mapper.writeValueAsString(fv), now.toEpochMilli()));
                }
            } catch (Exception e) {
                log.error("Error computing features", e);
            }
        }

        private double calcStdDev(List<Long> values) {
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
