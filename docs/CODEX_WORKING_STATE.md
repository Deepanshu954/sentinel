# Codex Working State (Persistent Memory)

Purpose: keep a local, continuously updated state so future sessions do not need full re-analysis.

Last updated: 2026-04-18
Owner: Codex + Deepanshu

## Product Goal
Sentinel should operate as a real protective autoscaling control layer:
- anticipate load spikes,
- avoid crashes,
- keep latency stable,
- and trigger real infrastructure scaling with realistic provisioning delay.

## Current Snapshot
- Core local stack runs and validation script can pass.
- Confidence threshold defaults have been moved to `0.75`.
- Demo script parsing bug was addressed.
- Major gap remains: scaling action is still Redis pub/sub only, not cloud execution.

## Non-Negotiable Next Milestones
1. Real Action Execution
   - Convert dispatch from simulated Redis-only action to real scaler adapter.
   - First real target: AWS Auto Scaling Group (ASG) desired capacity updates.

2. Realistic Demo Scenarios
   - Extend `scripts/demo.sh` into a scenario runner with:
     - baseline traffic,
     - flash crowd,
     - second-wave spike,
     - recovery with safe scale-in hold.
   - Include infrastructure provisioning lag in the evaluation.

3. Paper-Parity ML Track
   - Current system is mostly XGBoost + bounds.
   - Add true parallel branch (LSTM) and calibrated ensemble gate logic if paper-level parity is required.

## Open Gaps To Track
- AWS adapter not yet implemented.
- True LSTM + XGBoost + meta-learner parity not implemented.
- Infrastructure-state features are partially synthetic/placeholder in stream extraction.
- Test suite quality and determinism still need hardening.

## Quick Delta Workflow (No Full Re-Read)
When changes happen, update only:
1. Changed files list
2. Behavior changes
3. Test evidence

Template to append below:

```
## Delta Update <date>
- Files changed:
  - <absolute/or-relative-path>
- What changed:
  - ...
- Validation run:
  - <command> -> <pass/fail + summary>
- Risks introduced:
  - ...
```

## Immediate Build Target
Demo command should eventually support:

`bash scripts/demo.sh --mode aws --asg-name <name> --region <region>`

Expected behavior:
- generate controlled load,
- Sentinel predicts surge,
- Sentinel dispatches scale action,
- adapter calls AWS ASG desired capacity,
- dashboard + logs show lead time and latency impact.

## Delta Update 2026-04-18 (Post-Remediation + New Plan)
- Files changed:
  - `REMEDIATION_REPORT.md`
  - `docs/NEXT_PROMPT_LOCAL_AUTOSCALING.md`
- What changed:
  - Remediation phase executed by agent and documented.
  - New next-phase prompt created for local-first real autoscaling demo (no AWS spend required now).
  - Plan now explicitly separates:
    - Local real scaling execution (immediate),
    - AWS adapter seam (future).
- Validation run:
  - Delta review from `REMEDIATION_REPORT.md` completed.
  - Key config checks confirm threshold at `0.75` and no hardcoded `@Deepanshu95`.
- Risks introduced:
  - Working tree is currently dirty with multiple modified files; avoid accidental reverts.

## Delta Update 2026-04-18 (Dataset Expansion)
- Files changed:
  - `docs/DATASET_SHORTLIST_2026.md`
  - `ml-service/scripts/dataset_manifest.json`
  - `ml-service/scripts/build_multisource_training_data.py`
  - `docs/NEXT_PROMPT_DATASET_UPGRADE.md`
- What changed:
  - Added curated high-quality/high-volume dataset shortlist with official sources.
  - Added manifest-driven multi-source dataset configuration for Sentinel ML pipeline.
  - Added local-first multi-source training-data builder script.
  - Added new prompt focused on integrating these datasets into production-grade preprocessing.
- Validation run:
  - Static validation only (no heavy dataset downloads executed).
- Risks introduced:
  - Adapters for each external dataset schema are still pending; manifest expects locally staged normalized files.

## Delta Update 2026-04-18 (Multi-Source Dataset Pipeline Implemented)
- Files changed:
  - `ml-service/scripts/adapters/__init__.py` (NEW - adapter registry)
  - `ml-service/scripts/adapters/base.py` (NEW - base adapter + GenericCSV)
  - `ml-service/scripts/adapters/wikimedia.py` (NEW)
  - `ml-service/scripts/adapters/azure.py` (NEW - Functions + VM)
  - `ml-service/scripts/adapters/google_cluster.py` (NEW)
  - `ml-service/scripts/adapters/alibaba.py` (NEW)
  - `ml-service/scripts/data_quality.py` (NEW - quality report generator)
  - `ml-service/scripts/build_multisource_training_data.py` (REWRITE - self-contained)
  - `ml-service/scripts/dataset_manifest.json` (ENHANCED - weight/tz/filter/clip/policy)
  - `ml-service/scripts/tests/test_dataset_pipeline.py` (NEW - 15 tests)
  - `scripts/train.sh` (MODIFIED - USE_MULTISOURCE_DATA flag)
  - `Makefile` (MODIFIED - train-multisource target)
  - `docs/service_ml.md` (MODIFIED - ingestion section)
  - `docs/DATASET_PREP_GUIDE.md` (NEW)
  - `README.md` (MODIFIED - dataset strategy section)
  - `DATASET_UPGRADE_REPORT.md` (NEW)
- What changed:
  - Full multi-source dataset ingestion pipeline implemented and tested.
  - 6 adapters (Wikimedia, Azure Functions, Azure VM, Google Cluster, Alibaba, Generic CSV).
  - Manifest-driven with per-source weight, timezone, filtering, clipping, missing data policy.
  - Dual fusion modes (sum / weighted_mean).
  - Deterministic synthetic fallback (seed-controlled).
  - Pre-training quality report (gaps, duplicates, outliers, source contributions).
- Validation run:
  - `python3 build_multisource_training_data.py` → 43200 rows, 26 features, quality report generated.
  - `pytest tests/test_dataset_pipeline.py -v` → 15/15 PASSED in 0.48s.
- Risks introduced:
  - Real dataset adapters tested against fixtures only (no full-scale dataset testing).
  - Infrastructure features remain partially synthetic when real InfluxDB telemetry is unavailable.

## Delta Update 2026-04-18 (Local Autoscaling Demo Implemented)
- Files changed:
  - `demo-backend/main.go`, `Dockerfile`, `go.mod` (NEW — scalable Go HTTP service)
  - `scaling-sidecar/app.py`, `Dockerfile`, `requirements.txt` (NEW — Docker socket bridge)
  - `orchestrator/.../scaling/ScalingExecutor.java` (NEW — interface)
  - `orchestrator/.../scaling/LocalDockerScalingExecutor.java` (NEW)
  - `orchestrator/.../scaling/AwsAsgScalingExecutor.java` (NEW — stub)
  - `orchestrator/.../scaling/ScalePolicy.java` (NEW — safety guardrails)
  - `orchestrator/.../scaling/ScalingConfig.java` (NEW — Spring config)
  - `orchestrator/.../ActionDispatcher.java` (REWRITE — executor + policy integration)
  - `orchestrator/.../PredictionScheduler.java` (MODIFIED — dispatch result)
  - `orchestrator/.../ScalingAction.java` (MODIFIED — new fields)
  - `orchestrator/application.yml` (MODIFIED — scaling config block)
  - `docker-compose.yml` (MODIFIED — demo-backend + scaling-sidecar services)
  - `scripts/demo.sh` (REWRITE — 5-phase scenario runner)
  - `infra/prometheus/prometheus.yml` (MODIFIED — demo-backend scrape)
  - `infra/grafana/dashboards/sentinel.json` (MODIFIED — 2 scaling panels)
  - `docs/local_autoscaling_demo.md` (NEW)
  - `docs/aws_future_activation.md` (NEW)
  - `README.md` (MODIFIED — autoscaling section)
  - `LOCAL_AUTOSCALING_DEMO_REPORT.md` (NEW)
- What changed:
  - Real autoscaling via Docker Compose replica scaling (not just Redis pub/sub).
  - ScalingExecutor interface with LocalDockerScalingExecutor (active) and AwsAsgScalingExecutor (stub).
  - ScalePolicy with cooldown (60s), hysteresis (500/200 thresholds), max step (2), min/max replicas (1/6).
  - 5-phase demo scenario: baseline → flash crowd → sustained → second wave → recovery.
  - Provisioning latency measured from scale request to healthy replicas.
  - New Prometheus metrics: desired/actual replicas, provisioning latency, decisions counter.
  - Grafana dashboard with Scaling Timeline panel.
- Validation:
  - demo-backend Go code compiles clean.
  - Gateway middleware tests pass.
  - validate_sentinel.sh compatibility preserved.
- Risks:
  - Requires Docker Desktop with socket access for scaling-sidecar.
  - Scale-in delay (120s) means recovery phase may not show scale-in in short demos.
  - AWS executor is a stub — requires SDK integration for production.

## Delta Update 2026-04-18 (Release-Hardening Pass)
- Files changed (high level):
  - `orchestrator/src/main/java/com/sentinel/scheduler/PredictionScheduler.java`
  - `orchestrator/src/main/java/com/sentinel/streaming/service/FeatureExtractionJob.java`
  - `orchestrator/src/main/java/com/sentinel/streaming/service/InfluxDBWriter.java`
  - `orchestrator/src/test/resources/application-test.yml`
  - `ml-service/scripts/adapters/apache_access.py` (NEW)
  - `ml-service/scripts/adapters/wikimedia.py`
  - `ml-service/scripts/adapters/__init__.py`
  - `ml-service/scripts/tests/test_dataset_pipeline.py`
  - `ml-service/scripts/dataset_manifest.json`
  - `scripts/fetch_public_datasets.sh` (NEW)
  - `scripts/train.sh`
  - `.gitignore`, `Makefile`, `README.md`, `docs/DATASET_PREP_GUIDE.md`, `docs/PROJECT_INDEX.md`
- Repo hygiene changes:
  - Moved root reports into `docs/reports/`.
  - Removed tracked duplicate/local-only files (`myenv`, `sentinel.env`, duplicate raw azure CSV paths, processed parquet artifact).
  - Added `.gitkeep` placeholders under `ml-service/data/raw` and `ml-service/data/processed`.
- Validation intent:
  - Make Java tests deterministic by disabling scheduler/streaming workers in test profile.
  - Add direct local dataset bootstrap (NASA + Wikimedia) without Kaggle dependency.
