# Dataset Preparation Guide

This guide explains how to set up training data for Sentinel's ML pipeline, from single-source synthetic data to multi-source research-grade datasets.

---

## Quick Start

### Legacy Pipeline (Synthetic Data)
```bash
bash scripts/train.sh
```
Uses `ml-service/scripts/prepare_dataset.py` to generate 30 days of synthetic traffic with diurnal patterns and random surges.

### Multi-Source Pipeline
```bash
make datasets
USE_MULTISOURCE_DATA=1 bash scripts/train.sh
# or
make train-multisource
```
Uses `ml-service/scripts/build_multisource_training_data.py` to combine multiple real-world datasets via a manifest-driven pipeline.

---

## Directory Layout

```
ml-service/
├── data/
│   ├── raw/                        # ← Place raw dataset files here
│   │   ├── NASA_access_log_Jul95.gz
│   │   ├── NASA_access_log_Aug95.gz
│   │   ├── pageviews-20240101-000000.gz
│   │   ├── wikimedia_pageviews.csv
│   │   ├── azure_functions_invocations.csv
│   │   ├── azure_vm_v2.csv
│   │   ├── google_cluster_2019.csv
│   │   └── alibaba_cluster_2018.csv
│   └── processed/
│       ├── training_data.parquet   # Generated training data
│       └── dataset_quality_report.json
├── scripts/
│   ├── dataset_manifest.json       # Source configuration
│   ├── build_multisource_training_data.py
│   ├── data_quality.py
│   └── adapters/                   # Per-dataset preprocessors
│       ├── base.py
│       ├── apache_access.py
│       ├── wikimedia.py
│       ├── azure.py
│       ├── google_cluster.py
│       └── alibaba.py
└── model_weights/                  # Trained models (output)
```

---

## Supported Datasets

### Tier A — Recommended

#### 1. NASA HTTP Logs (Internet Traffic Archive)
| Field | Value |
|-------|-------|
| **Source** | https://ita.ee.lbl.gov/html/contrib/NASA-HTTP.html |
| **Adapter** | `apache_access` |
| **Expected Format** | Apache Common Log Format (plain or gzip) |
| **Use Case** | Real web request bursts and per-minute arrival modeling |

**Download:**
```bash
bash scripts/fetch_public_datasets.sh core
```

#### 2. Wikimedia Pageviews
| Field | Value |
|-------|-------|
| **Source** | https://dumps.wikimedia.org/other/pageviews/ |
| **License** | CC0 |
| **Adapter** | `wikimedia` |
| **Expected Format** | Either pre-processed CSV (`timestamp`,`views`) or raw hourly dump (`.gz`) |
| **Use Case** | Seasonality patterns, demand surge windows |

#### 3. Azure Functions 2019

| Field | Value |
|-------|-------|
| **Source** | https://github.com/Azure/AzurePublicDataset |
| **License** | CC-BY-4.0 (data), MIT (code) |
| **Adapter** | `azure_functions` |
| **Expected Columns** | `end_timestamp`, `invocations` |
| **Use Case** | Autoscaling signal engineering |

#### 4. Azure VM V2
| Field | Value |
|-------|-------|
| **Adapter** | `azure_vm` |
| **Expected Columns** | `timestamp_vm`, `avg_cpu` |
| **Multiplier** | `1500.0` (maps CPU fraction to req/s scale) |

#### 5. Google ClusterData 2019
| Field | Value |
|-------|-------|
| **Source** | https://github.com/google/cluster-data |
| **License** | CC-BY |
| **Adapter** | `google_cluster` |
| **Expected Columns** | `start_time`, `avg_cpu` |
| **Note** | Full dataset is 2.4 TB. Use Kaggle sample for local dev |

**Kaggle Sample:**
```
https://www.kaggle.com/datasets/derrickmwiti/google-2019-cluster-sample
```

#### 6. Alibaba Cluster Trace v2018
| Field | Value |
|-------|-------|
| **Source** | https://github.com/alibaba/clusterdata |
| **Adapter** | `alibaba` |
| **Expected Columns** | `time_stamp`, `cpu_util_percent` |
| **Note** | Some downloads require survey + research-use terms |

---

## Manifest Configuration

The manifest file (`ml-service/scripts/dataset_manifest.json`) controls which datasets are used and how they're processed.

### Top-Level Settings
```json
{
  "fusion_mode": "sum",           // "sum" or "weighted_mean"
  "synthetic_fallback": true,     // Use synthetic data if no real sources load
  "synthetic_seed": 42,           // Deterministic seed for synthetic generation
  "output_path": "ml-service/data/processed/training_data.parquet",
  "quality_report_path": "ml-service/data/processed/dataset_quality_report.json"
}
```

### Per-Source Settings
```json
{
  "name": "azure_functions_2019",
  "enabled": true,                 // Toggle this source on/off
  "adapter": "azure_functions",    // Adapter from registry
  "path": "ml-service/data/raw/azure_functions_invocations.csv",
  "timestamp_col": "end_timestamp",
  "value_col": "invocations",
  "resample": "1min",              // Resample interval
  "agg": "sum",                    // Aggregation: sum, mean, max, min
  "multiplier": 1.0,               // Scale factor
  "weight": 1.5,                   // Weight for weighted_mean fusion
  "timezone": "UTC",               // Source timezone (converted to UTC)
  "filter_start": "2019-01-01",    // Optional: only use data after this date
  "filter_end": "2019-12-31",      // Optional: only use data before this date
  "clip_min": 0.0,                 // Optional: minimum value clamp
  "clip_max": null,                // Optional: maximum value clamp
  "missing_data_policy": "interpolate"  // drop | zero | ffill | interpolate
}
```

### Fusion Modes
- **`sum`** — Adds all source values at each timestamp. Best when sources represent complementary traffic (e.g., different API endpoints).
- **`weighted_mean`** — Weighted average using per-source `weight` field. Best when sources represent the same signal measured differently.

---

## Quality Report

After building the dataset, a quality report is generated at `ml-service/data/processed/dataset_quality_report.json`.

The report includes:
| Check | Description |
|-------|-------------|
| `total_rows` | Number of training samples |
| `date_range` | Start/end timestamps and span |
| `timestamp_continuity` | Gaps larger than 2× resample interval |
| `duplicate_timestamps` | Exact duplicate timestamps |
| `outlier_ratio` | % of values > 3σ from rolling median |
| `source_contributions` | % of data from each source |
| `null_counts` | Per-column NULL counts |

---

## Adding a Custom Dataset

1. Place your raw file in `ml-service/data/raw/`
2. If it's a simple CSV with `timestamp` + `value` columns, use `adapter: "generic"`
3. For complex formats, create a new adapter in `ml-service/scripts/adapters/`
4. Add an entry to `dataset_manifest.json`
5. Set `"enabled": true`
6. Run: `python3 ml-service/scripts/build_multisource_training_data.py`

Tip: by default, sources are disabled and `synthetic_fallback` is enabled. This keeps local runs safe on a laptop when optional datasets are missing.

---

## Running Tests
```bash
python3 -m pytest ml-service/scripts/tests/test_dataset_pipeline.py -v
```

---

## Future: AWS-Scale Extension
The pipeline is designed to run locally on a MacBook. For production-scale datasets (e.g., full Google ClusterData at 2.4 TB):
1. Use AWS S3 as raw data storage
2. Run `build_multisource_training_data.py` on an EC2/SageMaker instance
3. Push trained models to S3, pull into Docker build
