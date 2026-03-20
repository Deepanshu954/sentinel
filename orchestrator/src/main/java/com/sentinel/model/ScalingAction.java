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
}
