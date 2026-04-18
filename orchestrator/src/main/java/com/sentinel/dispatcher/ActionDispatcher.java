package com.sentinel.dispatcher;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sentinel.client.MLServiceClient.PredictionResponse;
import com.sentinel.scaling.ScalePolicy;
import com.sentinel.scaling.ScalePolicy.ScaleDecision;
import com.sentinel.scaling.ScalingExecutor;
import com.sentinel.scaling.ScalingExecutor.ScaleResult;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

@Component
public class ActionDispatcher {
    private static final Logger logger = LoggerFactory.getLogger(ActionDispatcher.class);

    private final StringRedisTemplate redisTemplate;
    private final MeterRegistry meterRegistry;
    private final ObjectMapper objectMapper;
    private final ScalingExecutor scalingExecutor;
    private final ScalePolicy scalePolicy;
    private final AtomicReference<Double> desiredReplicasGauge;
    private final AtomicReference<Double> actualReplicasGauge;

    public ActionDispatcher(StringRedisTemplate redisTemplate,
                            MeterRegistry meterRegistry,
                            ObjectMapper objectMapper,
                            ScalingExecutor scalingExecutor,
                            ScalePolicy scalePolicy,
                            @Qualifier("desiredReplicasGauge") AtomicReference<Double> desiredReplicasGauge,
                            @Qualifier("actualReplicasGauge") AtomicReference<Double> actualReplicasGauge) {
        this.redisTemplate = redisTemplate;
        this.meterRegistry = meterRegistry;
        this.objectMapper = objectMapper;
        this.scalingExecutor = scalingExecutor;
        this.scalePolicy = scalePolicy;
        this.desiredReplicasGauge = desiredReplicasGauge;
        this.actualReplicasGauge = actualReplicasGauge;
    }

    /**
     * Dispatch result containing scaling metadata for audit trail.
     */
    public record DispatchResult(
        int desiredReplicas,
        int actualReplicas,
        long provisioningLatencyMs,
        String scalerMode,
        String scaleAction
    ) {}

    /**
     * Execute a dispatch action: evaluate scaling policy, execute scaling if needed,
     * and continue existing Redis pub/sub notification.
     */
    public DispatchResult dispatch(PredictionResponse prediction) {
        DispatchResult result;

        try {
            // 1. Evaluate scaling policy (cooldown, thresholds, hysteresis)
            ScaleDecision decision = scalePolicy.evaluate(prediction.predicted_req_rate());
            logger.info("ScalePolicy decision: action={}, current={}, target={}, reason={}",
                    decision.action(), decision.currentReplicas(), decision.targetReplicas(), decision.reason());

            // 2. Execute scaling if policy says so
            int desiredReplicas = decision.targetReplicas();
            int actualReplicas = decision.currentReplicas();
            long provisioningMs = 0;
            String scaleAction = decision.action();

            if ("SCALE_OUT".equals(decision.action())) {
                ScaleResult scaleResult = scalingExecutor.executeScaleOut(
                        decision.currentReplicas(), decision.targetReplicas());
                if (scaleResult.success()) {
                    scalePolicy.recordScaleAction(scaleResult.desiredReplicas());
                    actualReplicas = scaleResult.actualReplicas();
                    provisioningMs = scaleResult.provisioningLatencyMs();
                }
                meterRegistry.counter("sentinel_scaling_decisions_total", "action", "SCALE_OUT").increment();

            } else if ("SCALE_IN".equals(decision.action())) {
                ScaleResult scaleResult = scalingExecutor.executeScaleIn(
                        decision.currentReplicas(), decision.targetReplicas());
                if (scaleResult.success()) {
                    scalePolicy.recordScaleAction(scaleResult.desiredReplicas());
                    actualReplicas = scaleResult.actualReplicas();
                    provisioningMs = scaleResult.provisioningLatencyMs();
                }
                meterRegistry.counter("sentinel_scaling_decisions_total", "action", "SCALE_IN").increment();

            } else if ("COOLDOWN".equals(decision.action())) {
                meterRegistry.counter("sentinel_scaling_decisions_total", "action", "COOLDOWN").increment();
            } else {
                meterRegistry.counter("sentinel_scaling_decisions_total", "action", "HOLD").increment();
            }

            // Update Prometheus gauges
            desiredReplicasGauge.set((double) desiredReplicas);
            actualReplicasGauge.set((double) Math.max(actualReplicas, 0));

            // Record provisioning latency histogram
            if (provisioningMs > 0) {
                meterRegistry.timer("sentinel_scaling_provisioning_latency_seconds")
                        .record(provisioningMs, TimeUnit.MILLISECONDS);
            }

            result = new DispatchResult(desiredReplicas, actualReplicas, provisioningMs, "local", scaleAction);

            // 3. Redis pub/sub notification (existing behavior, preserved)
            redisTemplate.opsForValue().set("sentinel:cache:prewarm:status", "active", 300, TimeUnit.SECONDS);

            Map<String, Object> payload = new HashMap<>();
            payload.put("action", scaleAction);
            payload.put("predicted_rate", prediction.predicted_req_rate());
            payload.put("confidence", prediction.confidence());
            payload.put("desired_replicas", desiredReplicas);
            payload.put("actual_replicas", actualReplicas);
            payload.put("provisioning_latency_ms", provisioningMs);
            payload.put("timestamp", Instant.now().toEpochMilli());

            String jsonPayload = objectMapper.writeValueAsString(payload);
            redisTemplate.convertAndSend("scaling.actions", jsonPayload);

            logger.info("DISPATCH: {} | predicted_rate={} | replicas {}->{} | latency={}ms",
                    scaleAction, prediction.predicted_req_rate(), decision.currentReplicas(),
                    desiredReplicas, provisioningMs);

            // Micrometer counter for backwards compatibility
            meterRegistry.counter("sentinel_scaling_actions_total", "action", "DISPATCH").increment();

        } catch (Exception e) {
            logger.error("Failed to execute dispatch: {}", e.getMessage());
            result = new DispatchResult(0, 0, 0, "local", "ERROR");
        }

        return result;
    }
}
