package com.sentinel.scaling;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Instant;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/**
 * ScalePolicy enforces safety guardrails for autoscaling decisions.
 * <p>
 * Prevents thrashing via cooldown timers, hysteresis thresholds,
 * max step size limits, and min/max replica bounds.
 */
public class ScalePolicy {
    private static final Logger logger = LoggerFactory.getLogger(ScalePolicy.class);

    private final int minReplicas;
    private final int maxReplicas;
    private final int cooldownSeconds;
    private final int maxStepSize;
    private final double scaleOutRateThreshold;
    private final double scaleInRateThreshold;
    private final int scaleInDelaySeconds;

    private final AtomicReference<Instant> lastScaleAction = new AtomicReference<>(Instant.EPOCH);
    private final AtomicReference<Instant> lastScaleInEligible = new AtomicReference<>(Instant.EPOCH);
    private final AtomicInteger currentReplicas = new AtomicInteger(1);

    public ScalePolicy(int minReplicas, int maxReplicas, int cooldownSeconds,
                       int maxStepSize, double scaleOutRateThreshold,
                       double scaleInRateThreshold, int scaleInDelaySeconds) {
        this.minReplicas = minReplicas;
        this.maxReplicas = maxReplicas;
        this.cooldownSeconds = cooldownSeconds;
        this.maxStepSize = maxStepSize;
        this.scaleOutRateThreshold = scaleOutRateThreshold;
        this.scaleInRateThreshold = scaleInRateThreshold;
        this.scaleInDelaySeconds = scaleInDelaySeconds;
    }

    /**
     * Evaluate predicted rate and decide on scaling action.
     *
     * @param predictedRate the ML model's predicted request rate
     * @return scaling decision with action and target replicas
     */
    public ScaleDecision evaluate(double predictedRate) {
        int current = currentReplicas.get();
        Instant now = Instant.now();

        // Check cooldown
        Instant lastAction = lastScaleAction.get();
        long secondsSinceLastAction = now.getEpochSecond() - lastAction.getEpochSecond();
        if (secondsSinceLastAction < cooldownSeconds) {
            long remaining = cooldownSeconds - secondsSinceLastAction;
            logger.debug("COOLDOWN: {}s remaining before next scale action allowed", remaining);
            return new ScaleDecision("COOLDOWN", current, current,
                    String.format("cooldown_active (%ds remaining)", remaining));
        }

        // Scale-out check (above threshold)
        if (predictedRate > scaleOutRateThreshold) {
            int needed = computeDesiredReplicas(predictedRate);
            int delta = Math.min(needed - current, maxStepSize);
            int target = Math.min(current + delta, maxReplicas);

            if (target > current) {
                logger.info("SCALE_OUT: rate={} > threshold={}, {} → {} replicas",
                        predictedRate, scaleOutRateThreshold, current, target);
                return new ScaleDecision("SCALE_OUT", current, target,
                        String.format("predicted_rate=%.0f > threshold=%.0f", predictedRate, scaleOutRateThreshold));
            }
            // Already at max
            return new ScaleDecision("HOLD", current, current,
                    String.format("at_max_replicas (%d)", maxReplicas));
        }

        // Scale-in check (below lower threshold with delay)
        if (predictedRate < scaleInRateThreshold && current > minReplicas) {
            Instant eligibleSince = lastScaleInEligible.get();
            if (eligibleSince.equals(Instant.EPOCH)) {
                // First time below threshold — start the delay timer
                lastScaleInEligible.set(now);
                return new ScaleDecision("HOLD", current, current,
                        "scale_in_delay_started");
            }

            long eligibleDuration = now.getEpochSecond() - eligibleSince.getEpochSecond();
            if (eligibleDuration >= scaleInDelaySeconds) {
                int target = Math.max(current - maxStepSize, minReplicas);
                logger.info("SCALE_IN: rate={} < threshold={} for {}s, {} → {} replicas",
                        predictedRate, scaleInRateThreshold, eligibleDuration, current, target);
                lastScaleInEligible.set(Instant.EPOCH); // Reset
                return new ScaleDecision("SCALE_IN", current, target,
                        String.format("predicted_rate=%.0f < threshold=%.0f for %ds",
                                predictedRate, scaleInRateThreshold, eligibleDuration));
            }

            long remaining = scaleInDelaySeconds - eligibleDuration;
            return new ScaleDecision("HOLD", current, current,
                    String.format("scale_in_pending (%ds remaining)", remaining));
        } else {
            // Rate above scale-in threshold — reset the delay timer
            lastScaleInEligible.set(Instant.EPOCH);
        }

        return new ScaleDecision("HOLD", current, current, "within_thresholds");
    }

    /**
     * Compute desired replicas from predicted rate.
     * Simple formula: 1 replica per 500 rps baseline capacity.
     */
    private int computeDesiredReplicas(double predictedRate) {
        double capacityPerReplica = scaleOutRateThreshold; // Each replica handles up to threshold rps
        int needed = (int) Math.ceil(predictedRate / capacityPerReplica);
        return Math.max(minReplicas, Math.min(needed, maxReplicas));
    }

    /** Record that a scaling action was executed. */
    public void recordScaleAction(int newReplicaCount) {
        lastScaleAction.set(Instant.now());
        currentReplicas.set(newReplicaCount);
        lastScaleInEligible.set(Instant.EPOCH);
    }

    /** Update current replica count from external observation. */
    public void updateCurrentReplicas(int count) {
        currentReplicas.set(count);
    }

    public int getCurrentReplicas() {
        return currentReplicas.get();
    }

    // ── Decision record ──────────────────────────────────────────────────

    public record ScaleDecision(
        String action,       // SCALE_OUT | SCALE_IN | HOLD | COOLDOWN
        int currentReplicas,
        int targetReplicas,
        String reason
    ) {}
}
