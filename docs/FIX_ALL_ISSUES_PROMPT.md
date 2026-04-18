# Sentinel Finalization Prompt (Release + Paper-Gap Closure)

Use this prompt with an agentic coding assistant for the **next pass**.

---

You are a senior backend/platform + ML systems engineer.

Repository root: `/Users/deepanshu/Documents/GitHub/sentinel`

## Mission
Prepare Sentinel for a **push-ready, stable release today** while closing critical gaps between implementation and the research paper intent.

## Current Context (already implemented)
- Local autoscaling demo exists (`demo-backend` + `scaling-sidecar` + orchestrator scaling policy).
- Multi-source dataset pipeline exists (`build_multisource_training_data.py`, adapters, manifest, tests).
- Reports and indexing exist under `docs/`.

## Execute These Workstreams

### 1) Stability and Regression Safety (P0)
1. Run full checks:
   - `go test ./...` in `gateway`
   - `python3 -m pytest -q` in `ml-service/service`
   - `python3 -m pytest ml-service/scripts/tests/test_dataset_pipeline.py -q`
   - `mvn test` in `orchestrator`
2. Fix any failing test or flaky runtime behavior.
3. Ensure orchestrator tests do not start non-essential background workloads in test profile (scheduler/streaming workers should be toggleable).

### 2) Dataset Quality + Practical Local Workflow (P0)
1. Validate `scripts/fetch_public_datasets.sh` works from clean state.
2. Ensure `USE_MULTISOURCE_DATA=1 bash scripts/train.sh` completes with:
   - generated `ml-service/data/processed/training_data.parquet`
   - generated `ml-service/data/processed/dataset_quality_report.json`
3. Improve manifest defaults and docs if any source path/column mismatch appears.
4. Keep synthetic fallback reliable when optional datasets are absent.

### 3) Repo Hygiene / Industry Layout (P1)
1. Remove obsolete or duplicate files/folders.
2. Keep top-level clean (runtime essentials only).
3. Ensure `.gitignore` correctly excludes generated/cache/data artifacts.
4. Verify no credentials/secrets are hardcoded.
5. Ensure `docs/reports/` and `docs/PROJECT_INDEX.md` remain up to date.

### 4) Demo Reliability (P1)
1. Run `bash scripts/demo.sh` against running stack.
2. Verify at least one real scale action occurs (scale-out or scale-in).
3. Confirm summary output includes replica transitions and latency signals.
4. If demo fails, fix scripts/config and re-test.

### 5) Paper-Parity Gap Tracking (P2)
Document what remains vs paper (without fake claims):
- LSTM branch (currently missing or partial)
- true parallel ensemble weighting/calibration behavior
- production-scale validation limits (95M requests / 45 days)

## Acceptance Criteria
1. All local test suites above pass.
2. `scripts/train.sh` works in both legacy and multi-source modes.
3. `scripts/demo.sh` runs end-to-end locally and shows scaling behavior.
4. No hardcoded secrets found.
5. Repo structure is clean and push-ready.
6. Docs reflect real behavior.

## Deliverables
1. Updated code and docs.
2. Updated index:
   - `docs/PROJECT_INDEX.md`
3. Final report:
   - `docs/reports/FINAL_RELEASE_REPORT.md`
   including:
   - executed commands + outcomes
   - fixed issues
   - remaining known gaps
   - explicit “human-required” items.

## Human-Required / Non-Automatable Items (must be listed)
1. Rotating any real cloud/API credentials used outside local dev.
2. Running true production-scale benchmark for paper-level claims.
3. Final threshold/business policy sign-off for scaling aggressiveness.
4. Enabling and validating AWS ASG executor in real AWS account.
