package com.sentinel.scaling;

import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.concurrent.atomic.AtomicReference;

/**
 * Spring configuration that wires ScalingExecutor and ScalePolicy
 * based on environment variables.
 */
@Configuration
public class ScalingConfig {
    private static final Logger logger = LoggerFactory.getLogger(ScalingConfig.class);

    @Value("${sentinel.scaling.mode:local}")
    private String scalerMode;

    @Value("${sentinel.scaling.sidecar-url:http://scaling-sidecar:5050}")
    private String sidecarUrl;

    @Value("${sentinel.scaling.target-service:demo-backend}")
    private String targetService;

    @Value("${sentinel.scaling.min-replicas:1}")
    private int minReplicas;

    @Value("${sentinel.scaling.max-replicas:6}")
    private int maxReplicas;

    @Value("${sentinel.scaling.cooldown-seconds:60}")
    private int cooldownSeconds;

    @Value("${sentinel.scaling.max-step-size:2}")
    private int maxStepSize;

    @Value("${sentinel.scaling.scale-out-rate-threshold:500}")
    private double scaleOutRateThreshold;

    @Value("${sentinel.scaling.scale-in-rate-threshold:200}")
    private double scaleInRateThreshold;

    @Value("${sentinel.scaling.scale-in-delay-seconds:120}")
    private int scaleInDelaySeconds;

    // AWS config (future)
    @Value("${sentinel.scaling.aws.region:us-east-1}")
    private String awsRegion;

    @Value("${sentinel.scaling.aws.asg-name:}")
    private String awsAsgName;

    @Bean
    public ScalingExecutor scalingExecutor() {
        return switch (scalerMode.toLowerCase()) {
            case "aws" -> {
                logger.warn("AWS scaler mode selected — using stub implementation (NOT OPERATIONAL)");
                yield new AwsAsgScalingExecutor(awsRegion, awsAsgName);
            }
            case "local" -> {
                logger.info("Local Docker scaler mode. Sidecar={}, Target={}", sidecarUrl, targetService);
                yield new LocalDockerScalingExecutor(sidecarUrl, targetService);
            }
            default -> {
                logger.info("Unknown scaler mode '{}', defaulting to local", scalerMode);
                yield new LocalDockerScalingExecutor(sidecarUrl, targetService);
            }
        };
    }

    @Bean
    public ScalePolicy scalePolicy() {
        logger.info("ScalePolicy: min={}, max={}, cooldown={}s, maxStep={}, " +
                "outThreshold={}, inThreshold={}, inDelay={}s",
                minReplicas, maxReplicas, cooldownSeconds, maxStepSize,
                scaleOutRateThreshold, scaleInRateThreshold, scaleInDelaySeconds);
        return new ScalePolicy(
                minReplicas, maxReplicas, cooldownSeconds,
                maxStepSize, scaleOutRateThreshold,
                scaleInRateThreshold, scaleInDelaySeconds
        );
    }

    @Bean
    public AtomicReference<Double> desiredReplicasGauge(MeterRegistry meterRegistry) {
        AtomicReference<Double> ref = new AtomicReference<>(1.0);
        meterRegistry.gauge("sentinel_scaling_desired_replicas", ref, AtomicReference::get);
        return ref;
    }

    @Bean
    public AtomicReference<Double> actualReplicasGauge(MeterRegistry meterRegistry) {
        AtomicReference<Double> ref = new AtomicReference<>(1.0);
        meterRegistry.gauge("sentinel_scaling_actual_replicas", ref, AtomicReference::get);
        return ref;
    }
}
