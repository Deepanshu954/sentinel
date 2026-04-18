# Next Prompt: Multi-Dataset Upgrade for Sentinel (Local First)

Use this prompt with your agentic coding assistant.

---

You are a senior ML/platform engineer working on Sentinel.

Repository: `/Users/deepanshu/Documents/GitHub/sentinel`

## Objective
Upgrade Sentinel's training pipeline from limited/synthetic data to a **multi-source, research-grade dataset strategy** while keeping workflows runnable on a MacBook (no paid cloud dependency).

## Inputs Already Added
1. Dataset shortlist doc:
   - `docs/DATASET_SHORTLIST_2026.md`
2. Multi-source manifest:
   - `ml-service/scripts/dataset_manifest.json`
3. New builder script:
   - `ml-service/scripts/build_multisource_training_data.py`

## Required Work

### 1. Implement real adapters for high-value datasets
Add concrete preprocessors for:
- Wikimedia pageviews (pageview complete/hourly)
- Azure Functions 2019 trace
- Google ClusterData2019 (selected usage signals)
- Alibaba trace (v2018 or v2026-GenAI subset)

Each adapter must output standardized schema:
- `timestamp` (UTC)
- `value` (numeric rate/load signal)

### 2. Improve manifest-driven ingestion
Extend `dataset_manifest.json` support:
- optional timezone parsing
- optional filtering/window selection
- per-source weighting and clipping
- per-source missing-data handling policy

### 3. Build robust composite target series
In `build_multisource_training_data.py`:
- combine enabled sources into one canonical `req_rate_1m`
- support at least 2 fusion modes:
  - `sum`
  - `weighted_mean`
- add deterministic seed for any synthetic fallback

### 4. Wire into training flow
Update `scripts/train.sh` and/or Makefile so training can run with:
- legacy pipeline (existing)
- multi-source pipeline (new) via a flag (e.g., `USE_MULTISOURCE_DATA=1`)

### 5. Add quality checks
Create validation checks before training:
- timestamp continuity/gap report
- duplicate timestamps report
- outlier ratio
- source contribution percentages

Emit report to:
- `ml-service/data/processed/dataset_quality_report.json`

### 6. Add tests
Add tests for:
- manifest parsing
- adapter normalization
- merge/fusion behavior
- failure on missing required columns

### 7. Documentation
Update:
- `README.md` (dataset section + commands)
- `docs/service_ml.md` (new ingestion flow)
- Add `docs/DATASET_PREP_GUIDE.md` with:
  - where to place raw files
  - expected input columns per source
  - example manifest configurations

## Constraints
- No cloud services required to run default path.
- Keep backward compatibility for existing scripts.
- Avoid huge downloads in CI; use small fixture samples for tests.

## Acceptance Criteria
1. Multi-source build command runs:
   - `python3 ml-service/scripts/build_multisource_training_data.py`
2. Training succeeds from multi-source output:
   - `python3 ml-service/ml/train_xgboost.py`
   - `python3 ml-service/ml/train_isolation_forest.py`
3. Dataset quality report is generated.
4. Tests pass for new dataset ingestion components.
5. Docs clearly explain local workflow and future AWS-scale extension.

## Deliverable
Produce `DATASET_UPGRADE_REPORT.md` with:
- sources integrated
- preprocessing decisions
- data quality stats
- model metric changes vs legacy dataset path
- remaining gaps and next recommendations

