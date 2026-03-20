package com.sentinel.gate;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class ConfidenceGate {
    @Value("${sentinel.confidence.threshold:0.75}")
    private double threshold;

    @Value("${sentinel.rate.threshold:20}")
    private double rateThreshold;

    public GateDecision evaluate(double confidence, double predictedRate) {
        if (predictedRate < rateThreshold) {
            return new GateDecision("HOLD", "prediction_too_low", confidence);
        }
        
        if (confidence >= threshold) {
            return new GateDecision("DISPATCH", "confidence_met", confidence);
        } else {
            return new GateDecision("HOLD", "below_threshold", confidence);
        }
    }

    public void setThreshold(double threshold) {
        this.threshold = threshold;
    }

    public double getThreshold() {
        return this.threshold;
    }

    public record GateDecision(String action, String reason, double confidence) {}
}
