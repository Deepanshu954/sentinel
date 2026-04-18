# Next Prompt: Local-First Real Autoscaling Demo (No Cloud Spend)

Use this prompt with your agentic coding assistant for the next implementation phase.

---

You are a senior platform engineer working on Sentinel.

Repo root: `/Users/deepanshu/Documents/GitHub/sentinel`

## Context
- Previous remediation pass has already completed and is documented in `REMEDIATION_REPORT.md`.
- Current priority is **realistic autoscaling behavior on a MacBook only** (no paid AWS usage yet).
- AWS integration is still desired in the future, so design with a clean adapter seam now.

## Phase Goal
Deliver a **real-world-style local autoscaling demo** where `scripts/demo.sh` triggers load scenarios and Sentinel causes actual capacity changes (local container replicas) with realistic provisioning delay and safety guardrails.

## Non-Goals (for this phase)
- Do not require paid cloud services.
- Do not claim full paper parity metrics (95M requests / production economics) in this phase.
- Do not block implementation on LSTM branch.

## Required Outcomes
1. `scripts/demo.sh` demonstrates actual scale-out / scale-in effects locally.
2. Scaling actions are no longer only "log/pubsub simulation"; they result in observable replica changes.
3. Provisioning lag is modeled/measured (to mimic real infra startup delay).
4. System includes anti-thrashing safeguards (cooldown + min/max replicas + hysteresis).
5. Architecture is ready for later AWS adapter drop-in.

## Implementation Plan

### 1. Add Scaler Adapter Abstraction
Create an explicit interface in orchestrator:
- `ScalingExecutor` interface:
  - `executeScaleOut(...)`
  - `executeScaleIn(...)`
  - `health()`
- Implementations:
  - `LocalDockerScalingExecutor` (active now)
  - `AwsAsgScalingExecutor` (stub/placeholder with clear TODO)
- Controlled via env/config:
  - `SCALER_MODE=local|aws`

### 2. Implement Local Real Scaling Path
Use local Docker Compose scaling as the real action target:
- On DISPATCH, compute desired replica delta from predicted load and thresholds.
- Apply scaling to a demo backend service with:
  - min replicas: 1
  - max replicas: configurable (e.g. 6)
  - cooldown: configurable (e.g. 60–120s)
- Measure and log:
  - action dispatch time
  - desired replica count
  - observed replica count
  - provisioning latency

### 3. Add/Refine Demo Workload Service
If needed, introduce a dedicated `demo-app` service that can saturate and recover:
- Endpoint behavior should show realistic degradation under load (latency increase / occasional 5xx near capacity).
- Stateless so horizontal scaling helps.
- Expose simple metrics endpoint for request latency and errors.

### 4. Upgrade `scripts/demo.sh` into Scenario Runner
Support deterministic scenario phases:
1. Baseline steady load
2. Flash-crowd surge
3. Sustained pressure
4. Second-wave surge
5. Recovery/scale-in window

At the end, print:
- number of DISPATCH/HOLD decisions
- replica timeline
- p50/p95 latency by phase
- error rate by phase
- time-to-scale (dispatch -> first healthy extra replica)

### 5. Safety Logic (Must Have)
Add guardrails:
- Hysteresis thresholds for scale-out vs scale-in.
- Cooldown timers.
- Max step size per action.
- HOLD on low confidence or unstable predictions.

### 6. Observability Upgrades
Add/ensure metrics:
- `sentinel_scaling_desired_replicas`
- `sentinel_scaling_actual_replicas`
- `sentinel_scaling_provisioning_latency_seconds`
- `sentinel_scaling_decisions_total{action=...}`
- `sentinel_demo_phase_latency_seconds` (optional but useful)

Update Grafana dashboard with a “Scaling Timeline” panel.

### 7. Future AWS Seam (No Spend Yet)
Prepare but do not require AWS usage:
- `AwsAsgScalingExecutor` class with config placeholders:
  - `AWS_REGION`
  - `AWS_ASG_NAME`
- Return clear runtime warning if selected without credentials.
- Keep integration disabled by default.

## Acceptance Criteria
1. `bash scripts/demo.sh` runs end-to-end on local MacBook and finishes with a summary report.
2. During demo run, replica count changes at least once due to Sentinel decisioning.
3. Provisioning latency is reported as a measured value (not hardcoded).
4. No scaling thrash (no rapid oscillation in short intervals).
5. `go test ./...`, `pytest -q`, and `mvn test` (or documented profile equivalent) pass.
6. `bash scripts/validate_sentinel.sh` still passes after changes.

## Deliverables
1. Code changes + tests.
2. Updated `scripts/demo.sh`.
3. Updated docs:
   - how local autoscaling demo works,
   - limitations vs full research-paper scope,
   - AWS future activation guide.
4. New report file: `LOCAL_AUTOSCALING_DEMO_REPORT.md` with:
   - scenario timelines,
   - scaling events,
   - latency/error comparisons pre/post scale,
   - known limitations.

## Notes
- Prefer incremental commits by subsystem.
- Keep backwards compatibility for current local stack as much as possible.
- If any command requires elevated privileges or fails due Docker socket constraints, document and provide a local fallback.

