package com.sentinel.scaling;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * AWS Auto Scaling Group executor — PLACEHOLDER for future cloud integration.
 * <p>
 * This class is not operational. It exists to define the adapter seam
 * so that switching from local to AWS scaling requires only config changes.
 * <p>
 * Required environment variables (when activated):
 * <ul>
 *   <li>{@code AWS_REGION} — e.g., us-east-1</li>
 *   <li>{@code AWS_ASG_NAME} — Auto Scaling Group name</li>
 *   <li>Standard AWS credentials (IAM role, env vars, or ~/.aws/credentials)</li>
 * </ul>
 *
 * @see ScalingExecutor
 */
public class AwsAsgScalingExecutor implements ScalingExecutor {
    private static final Logger logger = LoggerFactory.getLogger(AwsAsgScalingExecutor.class);

    private final String region;
    private final String asgName;

    public AwsAsgScalingExecutor(String region, String asgName) {
        this.region = region;
        this.asgName = asgName;
        logger.warn("AwsAsgScalingExecutor initialized — THIS IS A STUB. " +
                "AWS scaling is not yet implemented. Region={}, ASG={}", region, asgName);
    }

    @Override
    public ScaleResult executeScaleOut(int currentReplicas, int desiredReplicas) {
        // TODO: Implement AWS Auto Scaling Group desired capacity update
        // AsgClient.setDesiredCapacity(SetDesiredCapacityRequest.builder()
        //     .autoScalingGroupName(asgName)
        //     .desiredCapacity(desiredReplicas)
        //     .build());
        logger.warn("AWS SCALE_OUT: Would set ASG '{}' desired capacity to {} (NOT IMPLEMENTED)", asgName, desiredReplicas);
        return new ScaleResult(false, desiredReplicas, -1, 0, "AWS scaling not implemented");
    }

    @Override
    public ScaleResult executeScaleIn(int currentReplicas, int desiredReplicas) {
        // TODO: Implement AWS Auto Scaling Group scale-in with termination policy
        logger.warn("AWS SCALE_IN: Would set ASG '{}' desired capacity to {} (NOT IMPLEMENTED)", asgName, desiredReplicas);
        return new ScaleResult(false, desiredReplicas, -1, 0, "AWS scaling not implemented");
    }

    @Override
    public ReplicaStatus getReplicaStatus() {
        // TODO: Query ASG DescribeAutoScalingGroups for instance count
        return new ReplicaStatus(-1, -1, "aws:" + asgName);
    }

    @Override
    public boolean isHealthy() {
        // TODO: Validate AWS credentials and ASG existence
        logger.warn("AWS health check: credentials and ASG validation not yet implemented");
        return false;
    }
}
