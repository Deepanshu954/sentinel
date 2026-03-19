package com.sentinel.streaming.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sentinel.streaming.model.FeatureVector;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.kstream.Consumed;
import org.apache.kafka.streams.kstream.Produced;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.Properties;

@Service
public class FeatureExtractionJob {

    private static final Logger log = LoggerFactory.getLogger(FeatureExtractionJob.class);

    private final ObjectMapper mapper;
    private final Properties kafkaStreamsProperties;
    private KafkaStreams streams;

    public FeatureExtractionJob(ObjectMapper mapper, @Qualifier("kafkaStreamsProperties") Properties kafkaStreamsProperties) {
        this.mapper = mapper;
        this.kafkaStreamsProperties = kafkaStreamsProperties;
    }

    @PostConstruct
    public void start() {
        StreamsBuilder builder = new StreamsBuilder();

        builder.stream("api.events", Consumed.with(Serdes.String(), Serdes.String()))
                .mapValues(value -> {
                    try {
                        log.debug("Consumed raw event json: {}", value);
                        JsonNode node = mapper.readTree(value);
                        String endpoint = node.has("endpoint") ? node.get("endpoint").asText() : "unknown";
                        long latency = node.has("latency_ms") ? node.get("latency_ms").asLong() : 0L;
                        
                        FeatureVector vector = new FeatureVector(
                                endpoint,
                                Instant.now(),
                                1,
                                (double) latency,
                                1.0
                        );
                        String result = mapper.writeValueAsString(vector);
                        log.info("Successfully produced simple feature vector for endpoint: {}", endpoint);
                        return result;
                    } catch (Exception e) {
                        log.warn("Ignored bad JSON payload during streams processing: {}", value);
                        return null;
                    }
                })
                .filter((key, value) -> value != null)
                .to("api.features", Produced.with(Serdes.String(), Serdes.String()));

        streams = new KafkaStreams(builder.build(), kafkaStreamsProperties);
        
        streams.setUncaughtExceptionHandler(e -> {
            log.error("Uncaught exception in Kafka Streams, replacing thread", e);
            return org.apache.kafka.streams.errors.StreamsUncaughtExceptionHandler.StreamThreadExceptionResponse.REPLACE_THREAD;
        });

        streams.start();
        log.info("Kafka Streams FeatureExtractionJob Service has successfully started.");
    }

    @PreDestroy
    public void stop() {
        if (streams != null) {
            log.info("Closing Kafka Streams processing application...");
            streams.close();
        }
    }
}
