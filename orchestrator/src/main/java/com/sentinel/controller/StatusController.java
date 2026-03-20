package com.sentinel.controller;

import com.sentinel.gate.ConfidenceGate;
import com.sentinel.model.ScalingAction;
import com.sentinel.repository.ScalingActionRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class StatusController {

    private final ScalingActionRepository scalingActionRepository;
    private final ConfidenceGate confidenceGate;
    private final long startTime = System.currentTimeMillis();

    @Value("${sentinel.polling.interval.ms:5000}")
    private long pollingIntervalMs;

    public StatusController(ScalingActionRepository scalingActionRepository, ConfidenceGate confidenceGate) {
        this.scalingActionRepository = scalingActionRepository;
        this.confidenceGate = confidenceGate;
    }

    @GetMapping("/status")
    public Map<String, Object> getStatus() {
        Map<String, Object> status = new HashMap<>();
        status.put("service", "sentinel-orchestrator");
        status.put("status", "ok");
        status.put("uptime_ms", System.currentTimeMillis() - startTime);

        List<ScalingAction> recentActions = scalingActionRepository.findTop50ByOrderByTimestampDesc();
        if (!recentActions.isEmpty()) {
            status.put("last_action", recentActions.get(0));
            status.put("last_prediction", recentActions.get(0));
        } else {
            status.put("last_action", null);
            status.put("last_prediction", null);
        }

        return status;
    }

    @GetMapping("/actions")
    public List<ScalingAction> getActions() {
        return scalingActionRepository.findTop50ByOrderByTimestampDesc();
    }

    @GetMapping("/config")
    public Map<String, Object> getConfig() {
        return Map.of(
            "confidence_threshold", confidenceGate.getThreshold(),
            "polling_interval_ms", pollingIntervalMs
        );
    }

    @PostMapping("/config")
    public Map<String, Object> updateConfig(@RequestBody Map<String, Double> payload) {
        if (payload.containsKey("confidence_threshold")) {
            confidenceGate.setThreshold(payload.get("confidence_threshold"));
        }
        return getConfig();
    }
}
