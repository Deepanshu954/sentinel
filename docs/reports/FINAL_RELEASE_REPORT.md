# Final Release Report

Date: 2026-04-18

## Scope Completed
- Stabilized orchestrator tests by making scheduler/streaming workers configurable and disabled in test profile.
- Added new dataset ingestion support for Apache access logs (NASA HTTP) and improved Wikimedia dump parsing.
- Added public dataset bootstrap script (`scripts/fetch_public_datasets.sh`) and wired commands into `Makefile` and `sentinel.sh`.
- Hardened ML dependency compatibility (`httpx<0.28.0` for FastAPI/Starlette test client compatibility).
- Fixed container training workflow so `make train` prepares data and persists trained models to runtime-mounted path.
- Cleaned repository hygiene:
  - removed obsolete tracked files (`myenv`, `sentinel.env`, duplicate raw azure copies, tracked processed parquet)
  - moved reports under `docs/reports/`
  - tightened `.gitignore` for generated artifacts.
- Updated docs/index/prompt files for current architecture and workflow.

## Verification Commands and Results
- `bash -n scripts/fetch_public_datasets.sh scripts/train.sh sentinel.sh scripts/demo.sh launch.sh` ✅
- `go test ./...` (gateway) ✅
- `go test ./...` (demo-backend) ✅
- `python3 -m pytest -q ml-service/scripts/tests/test_dataset_pipeline.py` ✅ (17 passed)
- `mvn -q test` (orchestrator) ✅
- `docker compose run --rm --user root ml-service sh -lc "pip install -q pytest && pytest -q service/test_main.py"` ✅ (7 passed)
- `bash scripts/fetch_public_datasets.sh core` ✅
- `python3 ml-service/scripts/build_multisource_training_data.py` ✅ (84,334 rows built from NASA + Wikimedia)
- `make train` ✅

## Known Residual Risks
- Local host execution of `ml-service/service/test_main.py` still depends on local OpenMP runtime (`libomp`) when using host Python/XGBoost.
- `scripts/train.sh` remains host-environment dependent when not using containerized training.
- Full end-to-end `scripts/demo.sh` requires all core services running (Docker resources/network).

## Human-Required Items
1. Rotate any externally used credentials/tokens if ever exposed.
2. Run production-scale benchmark (95M requests / 45 days) before claiming paper-level metrics.
3. Finalize scaling thresholds with business/SRE sign-off.
4. Enable and validate real AWS ASG execution path with cloud credentials and IAM policy.
