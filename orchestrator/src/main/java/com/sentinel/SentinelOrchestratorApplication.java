package com.sentinel;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * Sentinel Orchestrator — Spring Boot entry point.
 * Bootstraps Kafka Streams, Action Dispatching, and ML Pipelines.
 */
@SpringBootApplication
@EnableScheduling
public class SentinelOrchestratorApplication implements CommandLineRunner {

    private static final Logger logger = LoggerFactory.getLogger(SentinelOrchestratorApplication.class);

    @Value("${ML_SERVICE_URL:http://ml-service:8000}")
    private String mlServiceUrl;

    @Value("${sentinel.confidence.threshold:0.75}")
    private double confidenceThreshold;

    public static void main(String[] args) {
        SpringApplication.run(SentinelOrchestratorApplication.class, args);
    }

    @Override
    public void run(String... args) {
        logger.info("Sentinel Orchestrator started");
        logger.info("ML service URL: {}", mlServiceUrl);
        logger.info("Confidence threshold: {}", confidenceThreshold);
    }
}
