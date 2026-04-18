package com.sentinel.model;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "scaling_actions")
public class ScalingAction {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Instant timestamp;
    private String actionType; // DISPATCH | HOLD
    private double confidence;
    private double predictedRate;
    private String reason;
    private long durationMs;

    // ── New scaling fields ───────────────────────────────────────────────
    private int desiredReplicas;
    private int actualReplicas;
    private long provisioningLatencyMs;
    private String scalerMode;     // local | aws
    private String scaleAction;    // SCALE_OUT | SCALE_IN | HOLD | COOLDOWN

    // ── Getters/Setters ─────────────────────────────────────────────────

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Instant getTimestamp() { return timestamp; }
    public void setTimestamp(Instant timestamp) { this.timestamp = timestamp; }

    public String getActionType() { return actionType; }
    public void setActionType(String actionType) { this.actionType = actionType; }

    public double getConfidence() { return confidence; }
    public void setConfidence(double confidence) { this.confidence = confidence; }

    public double getPredictedRate() { return predictedRate; }
    public void setPredictedRate(double predictedRate) { this.predictedRate = predictedRate; }

    public String getReason() { return reason; }
    public void setReason(String reason) { this.reason = reason; }

    public long getDurationMs() { return durationMs; }
    public void setDurationMs(long durationMs) { this.durationMs = durationMs; }

    public int getDesiredReplicas() { return desiredReplicas; }
    public void setDesiredReplicas(int desiredReplicas) { this.desiredReplicas = desiredReplicas; }

    public int getActualReplicas() { return actualReplicas; }
    public void setActualReplicas(int actualReplicas) { this.actualReplicas = actualReplicas; }

    public long getProvisioningLatencyMs() { return provisioningLatencyMs; }
    public void setProvisioningLatencyMs(long provisioningLatencyMs) { this.provisioningLatencyMs = provisioningLatencyMs; }

    public String getScalerMode() { return scalerMode; }
    public void setScalerMode(String scalerMode) { this.scalerMode = scalerMode; }

    public String getScaleAction() { return scaleAction; }
    public void setScaleAction(String scaleAction) { this.scaleAction = scaleAction; }
}
