# Local Autoscaling Demo

How Sentinel's local autoscaling demo works, its architecture, how to run it, and its limitations.

---

## Overview

The local autoscaling demo runs entirely on your MacBook using Docker Compose. Instead of cloud infrastructure (AWS ASG), Sentinel scales Docker container replicas of a lightweight `demo-backend` service. The entire ML prediction → confidence gate → scaling action → provisioning cycle is real, with measured latency and observable replica changes.

## Architecture

```
                                              ┌──────────────────┐
  hey (load) ──► Gateway ──► demo-backend ◄───┤ Docker Compose   │
                    │              (1..6x)     │  scale command   │
                    ▼                          │                  │
               Kafka events                    └───────▲──────────┘
                    │                                  │
                    ▼                                  │ HTTP POST
            FeatureExtraction                          │ /scale
                    │                          ┌───────┴──────────┐
                    ▼                          │ scaling-sidecar   │
               InfluxDB                        │ (Docker socket)  │
                    │                          └──────────────────┘
                    ▼                                  ▲
           PredictionScheduler                         │
                    │                                  │
                    ▼                                  │
             ConfidenceGate ──► ActionDispatcher        │
              (DISPATCH/HOLD)    ├── ScalePolicy ──────┘
                    │            └── Redis Pub/Sub
                    ▼
             ScalingAction DB
```

### Key Components

| Component | Role |
|-----------|------|
| **demo-backend** | Lightweight Go HTTP service; scaling target (1–6 replicas) |
| **scaling-sidecar** | Python Flask service with Docker socket; executes `docker compose scale` |
| **ScalingExecutor** | Java interface with `LocalDockerScalingExecutor` implementation |
| **ScalePolicy** | Safety guardrails: cooldown, hysteresis, min/max, step size |
| **ActionDispatcher** | Orchestrates: evaluate policy → execute scaling → emit metrics → Redis pub/sub |

### Demo Backend Behavior

The `demo-backend` simulates realistic API load patterns:

| Concurrent Requests | Behavior |
|---------------------|----------|
| < 50 | Normal: 10–50ms latency, 200 OK |
| 50–100 | Under pressure: 50–200ms added latency |
| > 100 | Near capacity: 200–500ms latency + 5–50% error rate |

Horizontal scaling (more replicas) distributes the load, reducing per-instance concurrency and restoring normal latency.

---

## How to Run

### Prerequisites
- Docker Desktop running (macOS)
- `hey` HTTP load generator (`brew install hey`)
- Stack running (`./launch.sh`)

### Run the Demo
```bash
bash scripts/demo.sh
```

The demo runs 5 phases (~3.5 minutes total):

| Phase | Duration | Load | Expected Behavior |
|-------|----------|------|-------------------|
| 1. Baseline | 30s | ~20 rps | 1 replica, stable latency |
| 2. Flash Crowd | 45s | ~2000 rps | Scale-out triggered → 3–4 replicas |
| 3. Sustained | 30s | ~1500 rps | Replicas stable or +1 |
| 4. Second Wave | 30s | ~3000 rps | Scale-out → 5–6 replicas |
| 5. Recovery | 60s | ~10 rps | Cooldown active, eventual scale-in |

### What to Watch

1. **Terminal** — Live replica count updates + per-phase latency
2. **Grafana** — `http://localhost:3000` (admin/sentinel)
   - Scaling Timeline panel (desired vs actual replicas)
   - Request latency distribution
   - Scaling decisions counter

---

## Safety Guardrails

| Guard | Default | Purpose |
|-------|---------|---------|
| Min Replicas | 1 | Never scale below 1 |
| Max Replicas | 6 | Never exceed 6 (MacBook-friendly) |
| Cooldown | 60s | No scale action within 60s of last action |
| Max Step Size | 2 | Max ±2 replicas per action |
| Scale-Out Threshold | 500 rps | Predicted rate must exceed this to trigger scale-out |
| Scale-In Threshold | 200 rps | Predicted rate must drop below this for scale-in consideration |
| Scale-In Delay | 120s | Must remain below threshold for 2min before scale-in executes |

### Configuration

Override defaults via environment variables:
```bash
SCALING_MIN_REPLICAS=1 \
SCALING_MAX_REPLICAS=4 \
SCALING_COOLDOWN_SECONDS=30 \
bash scripts/demo.sh
```

---

## Limitations vs Full Paper Scope

| Aspect | Local Demo | Research Paper Target |
|--------|------------|----------------------|
| Scale target | Docker containers | AWS ASG / K8s HPA |
| Max replicas | 6 | Unlimited (cost-bounded) |
| Provisioning latency | ~2–5s (Docker) | 60–120s (EC2) |
| Load capacity | ~5K rps (MacBook) | 95M req/day |
| Traffic source | hey (synthetic) | Production API traffic |
| Cost optimization | Not applicable | Real $/hour tracking |
| LSTM branch | Not active | Required for paper parity |

The local demo validates the **decision architecture** (ML prediction → confidence gate → policy evaluation → execution) with real observable effects, while deferring production-scale economics to the AWS phase.

---

## Troubleshooting

### Docker Socket Permission Error
If the scaling-sidecar cannot access the Docker socket:
```bash
# Check socket permissions
ls -la /var/run/docker.sock
# On macOS Docker Desktop, this should work by default
```

### Replicas Not Changing
1. Check sidecar health: `curl http://localhost:5050/health`
2. Check orchestrator logs: `docker compose logs orchestrator -f`
3. Verify scaling config: `curl http://localhost:8090/api/config`

### High Latency / Errors
- Reduce `SCALING_MAX_REPLICAS` if your MacBook has limited resources
- Close resource-heavy applications during the demo
