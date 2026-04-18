# AWS Future Activation Guide

How to switch Sentinel from local Docker scaling to AWS Auto Scaling Groups (ASG) when ready for production deployment.

---

## Prerequisites

- AWS account with appropriate IAM permissions
- AWS CLI configured (`aws configure`)
- An existing Auto Scaling Group with launch template
- Sentinel orchestrator deployed with network access to AWS APIs

## Architecture Change

```
Local Mode:                           AWS Mode:
Orchestrator → Scaling Sidecar        Orchestrator → AWS ASG API
             → Docker Compose scale              → EC2 Instance Launch
             → Container replicas                → ELB Target Registration
```

## Configuration

### 1. Set Environment Variables

```bash
# In sentinel.env or docker-compose.yml
SCALER_MODE=aws
AWS_REGION=us-east-1
AWS_ASG_NAME=sentinel-backend-asg

# AWS credentials (prefer IAM roles in production)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

### 2. Update docker-compose.yml (or K8s deployment)

```yaml
orchestrator:
  environment:
    - SCALER_MODE=aws
    - AWS_REGION=${AWS_REGION}
    - AWS_ASG_NAME=${AWS_ASG_NAME}
```

### 3. Required IAM Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "autoscaling:SetDesiredCapacity",
        "autoscaling:DescribeAutoScalingGroups",
        "autoscaling:DescribeScalingActivities",
        "ec2:DescribeInstances"
      ],
      "Resource": "*"
    }
  ]
}
```

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| `ScalingExecutor` interface | ✅ Complete | Clean adapter seam |
| `LocalDockerScalingExecutor` | ✅ Complete | Active in local mode |
| `AwsAsgScalingExecutor` | ⬜ Stub only | TODOs in code; requires AWS SDK dependency |
| `ScalePolicy` | ✅ Complete | Shared across all executors |
| IAM policy | 📝 Documented | See above |
| Cost tracking | ⬜ Not started | Required for paper economics |

## Implementation Checklist (for AWS activation)

1. [ ] Add AWS SDK dependency to orchestrator `pom.xml`:
   ```xml
   <dependency>
       <groupId>software.amazon.awssdk</groupId>
       <artifactId>autoscaling</artifactId>
       <version>2.25.0</version>
   </dependency>
   ```

2. [ ] Implement `AwsAsgScalingExecutor.executeScaleOut()`:
   - Call `AsgClient.setDesiredCapacity()`
   - Poll `DescribeAutoScalingGroups` until InService count matches
   - Measure provisioning latency (expect 60–120s)

3. [ ] Implement `AwsAsgScalingExecutor.executeScaleIn()`:
   - Set desired capacity with appropriate termination policy
   - Wait for instance drain

4. [ ] Implement `AwsAsgScalingExecutor.isHealthy()`:
   - Validate credentials via STS `GetCallerIdentity`
   - Verify ASG exists via `DescribeAutoScalingGroups`

5. [ ] Add cost tracking:
   - Query EC2 pricing API for instance type
   - Log $/hour for current capacity
   - Emit `sentinel_scaling_hourly_cost_usd` Prometheus metric

6. [ ] Update Grafana with AWS-specific panels

7. [ ] Load test with realistic provisioning delay (60–120s warmup)

## Rollback

To switch back to local mode at any time:
```bash
SCALER_MODE=local docker compose up -d orchestrator
```

The `ScalePolicy` (cooldown, thresholds, hysteresis) remains the same across both modes. Only the execution layer changes.
