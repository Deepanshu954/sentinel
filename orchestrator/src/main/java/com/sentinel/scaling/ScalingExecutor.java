package com.sentinel.scaling;

/**
 * ScalingExecutor abstraction for Sentinel autoscaling.
 * <p>
 * Implementations handle the actual infrastructure scaling action:
 * - {@code LocalDockerScalingExecutor}: scales Docker Compose services locally
 * - {@code AwsAsgScalingExecutor}: (future) scales AWS Auto Scaling Groups
 * <p>
 * Selected via {@code SCALER_MODE} environment variable.
 */
public interface ScalingExecutor {

    /**
     * Execute a scale-out action (increase replicas).
     *
     * @param currentReplicas current running replica count
     * @param desiredReplicas target replica count
     * @return result containing success status and provisioning latency
     */
    ScaleResult executeScaleOut(int currentReplicas, int desiredReplicas);

    /**
     * Execute a scale-in action (decrease replicas).
     *
     * @param currentReplicas current running replica count
     * @param desiredReplicas target replica count (must be >= minReplicas)
     * @return result containing success status
     */
    ScaleResult executeScaleIn(int currentReplicas, int desiredReplicas);

    /**
     * Get current replica status for the scaling target.
     *
     * @return replica status with desired and running counts
     */
    ReplicaStatus getReplicaStatus();

    /**
     * Check if the scaling executor is healthy and able to execute actions.
     */
    boolean isHealthy();

    // ── Result records ──────────────────────────────────────────────────

    record ScaleResult(
        boolean success,
        int desiredReplicas,
        int actualReplicas,
        long provisioningLatencyMs,
        String message
    ) {}

    record ReplicaStatus(
        int desired,
        int running,
        String service
    ) {}
}
