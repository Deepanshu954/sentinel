package com.sentinel;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Sentinel Orchestrator — Spring Boot entry point.
 *
 * Starts the Spring context which bootstraps all components including
 * the Kafka Streams feature extraction pipeline and InfluxDB writer.
 */
@SpringBootApplication
public class SentinelOrchestratorApplication {

    public static void main(String[] args) {
        SpringApplication.run(SentinelOrchestratorApplication.class, args);
    }
}
