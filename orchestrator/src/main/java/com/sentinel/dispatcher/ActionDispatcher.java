package com.sentinel.dispatcher;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sentinel.client.MLServiceClient.PredictionResponse;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

@Component
public class ActionDispatcher {
    private static final Logger logger = LoggerFactory.getLogger(ActionDispatcher.class);
    
    private final StringRedisTemplate redisTemplate;
    private final MeterRegistry meterRegistry;
    private final ObjectMapper objectMapper;

    public ActionDispatcher(StringRedisTemplate redisTemplate, MeterRegistry meterRegistry, ObjectMapper objectMapper) {
        this.redisTemplate = redisTemplate;
        this.meterRegistry = meterRegistry;
        this.objectMapper = objectMapper;
    }

    public void dispatch(PredictionResponse prediction) {
        try {
            // Action 1: Redis cache pre-warm signals targeting 300s expiration wrapper logic constraints
            redisTemplate.opsForValue().set("sentinel:cache:prewarm:status", "active", 300, TimeUnit.SECONDS);
            
            // Action 2: Sequence Redis Pub/Sub stream payload broadcasts dynamically
            Map<String, Object> payload = new HashMap<>();
            payload.put("action", "scale_out");
            payload.put("predicted_rate", prediction.predicted_req_rate());
            payload.put("confidence", prediction.confidence());
            payload.put("timestamp", Instant.now().toEpochMilli());
            
            String jsonPayload = objectMapper.writeValueAsString(payload);
            redisTemplate.convertAndSend("scaling.actions", jsonPayload);
            
            // Action 3: Write robust log info records
            logger.info("DISPATCH: Action dispatched successfully. Payload: {}", jsonPayload);
            
            // Action 4: Instrument Micrometer counter natively targeting Prometheus output format 
            meterRegistry.counter("sentinel_scaling_actions_total", "action", "DISPATCH").increment();
            
        } catch (Exception e) {
            logger.error("Failed to execute dispatch actions over Redis limits: {}", e.getMessage());
        }
    }
}
