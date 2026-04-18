#!/usr/bin/env python3
"""
build_multisource_training_data.py — Sentinel Multi-Source Dataset Builder

Reads dataset_manifest.json, dispatches each enabled source to the correct
adapter, fuses the normalized time series, engineers 26 features, runs a
quality report, and writes training-ready parquet.

Usage:
    python3 ml-service/scripts/build_multisource_training_data.py
    python3 ml-service/scripts/build_multisource_training_data.py --manifest path/to/manifest.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# ── Resolve imports from scripts/ directory ──────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters import get_adapter
from data_quality import generate_quality_report


# ── 26-feature column list (canonical order) ─────────────────────────────
FEATURE_COLS = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "week_of_year",
    "is_weekend", "is_holiday", "day_of_month", "req_rate_1m", "req_rate_5m",
    "req_rate_15m", "req_rate_30m", "latency_std_5m", "latency_std_15m",
    "req_max_5m", "req_max_15m", "ewma_03", "ewma_07", "rate_of_change",
    "autocorr_lag1", "cpu_util", "memory_pressure", "active_connections",
    "cache_hit_ratio", "replica_count", "queue_depth",
]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Manifest Loading
# ═══════════════════════════════════════════════════════════════════════════

def load_manifest(manifest_path: Path) -> Dict[str, Any]:
    """Load and validate the dataset manifest JSON."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Validate required top-level keys
    if "sources" not in cfg or not isinstance(cfg["sources"], list):
        raise ValueError("Manifest must contain a 'sources' array.")

    return cfg


# ═══════════════════════════════════════════════════════════════════════════
# 2. Source Ingestion via Adapters
# ═══════════════════════════════════════════════════════════════════════════

def ingest_sources(cfg: Dict[str, Any]) -> tuple[List[pd.DataFrame], Dict[str, int]]:
    """Load each enabled source through its adapter. Returns frames + contributions."""
    enabled = [s for s in cfg["sources"] if s.get("enabled", False)]
    if not enabled:
        raise RuntimeError("No enabled sources in manifest.")

    frames: List[pd.DataFrame] = []
    contributions: Dict[str, int] = {}

    print(f"\n{'='*60}")
    print(f"  Loading {len(enabled)} enabled source(s)")
    print(f"{'='*60}")

    for source in enabled:
        adapter = get_adapter(source)
        df = adapter.load()
        if not df.empty:
            # Tag with weight for weighted_mean fusion
            df["_weight"] = adapter.weight
            df["_source"] = adapter.name
            frames.append(df)
            contributions[adapter.name] = len(df)

    return frames, contributions


# ═══════════════════════════════════════════════════════════════════════════
# 3. Synthetic Fallback Generator
# ═══════════════════════════════════════════════════════════════════════════

def generate_synthetic(seed: int = 42, days: int = 30) -> pd.DataFrame:
    """Deterministic synthetic traffic data when no real sources are available."""
    print("\n  ⚠ No real sources loaded — using synthetic fallback")
    np.random.seed(seed)

    N = days * 24 * 60  # 1-minute resolution
    timestamps = [datetime(2024, 1, 1) + timedelta(minutes=i) for i in range(N)]

    base_rate = 1000.0
    hour = np.array([t.hour for t in timestamps])
    dow = np.array([t.weekday() for t in timestamps])

    # Diurnal pattern: business hours 3x, night 0.2x
    rate = np.full(N, base_rate)
    rate[(hour >= 8) & (hour <= 18) & (dow < 5)] *= 3.0
    rate[(hour >= 2) & (hour <= 6)] *= 0.2
    rate[dow >= 5] *= 0.6

    # Noise ±15%
    rate *= np.random.uniform(0.85, 1.15, N)

    # 5 random surges
    for _ in range(5):
        idx = np.random.randint(0, N - 40)
        dur = np.random.randint(20, 41)
        rate[idx:idx + dur] *= np.random.uniform(5.0, 10.0)

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(timestamps, utc=True),
        "value": rate,
        "_weight": 1.0,
        "_source": "synthetic",
    })
    return df


# ═══════════════════════════════════════════════════════════════════════════
# 4. Fusion — Combine Multiple Sources
# ═══════════════════════════════════════════════════════════════════════════

def fuse_sources(
    frames: List[pd.DataFrame], mode: str = "sum"
) -> pd.DataFrame:
    """Merge all source DataFrames into a single time series.

    Modes:
        sum           — total value at each timestamp
        weighted_mean — weighted average using per-source _weight column
    """
    if not frames:
        return pd.DataFrame(columns=["timestamp", "req_rate_1m"])

    merged = pd.concat(frames, ignore_index=True)

    if mode == "weighted_mean":
        merged["_wv"] = merged["value"] * merged["_weight"]
        agg = merged.groupby("timestamp", as_index=False).agg(
            wv_sum=("_wv", "sum"),
            w_sum=("_weight", "sum"),
        )
        agg["req_rate_1m"] = agg["wv_sum"] / agg["w_sum"].clip(lower=1e-9)
        result = agg[["timestamp", "req_rate_1m"]].sort_values("timestamp")
    else:  # default: sum
        result = (
            merged.groupby("timestamp", as_index=False)["value"]
            .sum()
            .rename(columns={"value": "req_rate_1m"})
            .sort_values("timestamp")
        )

    return result.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════
# 5. Feature Engineering — Compute All 26 Features
# ═══════════════════════════════════════════════════════════════════════════

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the canonical 26-feature vector from a (timestamp, req_rate_1m) series."""
    print("\n  Computing 26 features...")

    ts = pd.to_datetime(df["timestamp"])
    r = df["req_rate_1m"].values
    r_series = pd.Series(r)

    # ── Temporal (8 features) ────────────────────────────────────────────
    h = ts.dt.hour
    dow = ts.dt.dayofweek

    df["hour_sin"] = np.sin(2 * np.pi * h / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * h / 24.0)
    df["dow_sin"] = np.sin(2 * np.pi * dow / 7.0)
    df["dow_cos"] = np.cos(2 * np.pi * dow / 7.0)
    df["week_of_year"] = ts.dt.isocalendar().week.astype(float).values
    df["is_weekend"] = (dow >= 5).astype(float)
    df["is_holiday"] = 0.0
    df["day_of_month"] = ts.dt.day.astype(float)

    # ── Statistical (12 features) ────────────────────────────────────────
    df["req_rate_5m"] = r_series.rolling(5, min_periods=1).mean().values
    df["req_rate_15m"] = r_series.rolling(15, min_periods=1).mean().values
    df["req_rate_30m"] = r_series.rolling(30, min_periods=1).mean().values

    # Latency proxy: model as correlated noise from request rate
    np.random.seed(99)
    base_latency = 10.0 + (r / r.max() if r.max() > 0 else 0) * 90.0
    base_latency += np.random.normal(0, 5.0, len(r))
    latency_series = pd.Series(np.maximum(base_latency, 1.0))
    df["latency_std_5m"] = latency_series.rolling(5, min_periods=1).std().fillna(0).values
    df["latency_std_15m"] = latency_series.rolling(15, min_periods=1).std().fillna(0).values

    df["req_max_5m"] = r_series.rolling(5, min_periods=1).max().values
    df["req_max_15m"] = r_series.rolling(15, min_periods=1).max().values
    df["ewma_03"] = r_series.ewm(alpha=0.3, adjust=False).mean().values
    df["ewma_07"] = r_series.ewm(alpha=0.7, adjust=False).mean().values

    prev = r_series.shift(1).fillna(r[0] if len(r) > 0 else 0)
    df["rate_of_change"] = ((r_series - prev) / np.maximum(prev, 1.0)).values
    df["autocorr_lag1"] = r_series.rolling(60, min_periods=2).corr(r_series.shift(1)).fillna(0).values

    # ── Infra State (6 features) ─────────────────────────────────────────
    # Synthetic infra features derived from load pattern
    np.random.seed(101)
    load_norm = r / (r.max() if r.max() > 0 else 1.0)
    df["cpu_util"] = np.clip(0.1 + load_norm * 0.7 + np.random.normal(0, 0.05, len(r)), 0.05, 0.99)
    df["memory_pressure"] = np.clip(df["cpu_util"].values * np.random.uniform(0.8, 1.2, len(r)), 0.05, 0.99)
    df["active_connections"] = np.maximum(r * np.random.uniform(0.1, 0.3, len(r)), 1.0)
    df["cache_hit_ratio"] = np.random.uniform(0.4, 0.9, len(r))
    df["replica_count"] = np.ones(len(r))
    df["queue_depth"] = np.maximum(load_norm * np.random.uniform(0, 10, len(r)), 0)

    # ── Target label ─────────────────────────────────────────────────────
    df["future_req_rate_5m"] = r_series.shift(-5).fillna(r[-1] if len(r) > 0 else 0.0).values

    # ── Surge label ──────────────────────────────────────────────────────
    baseline = float(r_series.median()) if len(r_series) > 0 else 1.0
    threshold = max(1.0, baseline * 3.0)
    df["is_surge"] = (r_series > threshold).astype(float).values

    return df


# ═══════════════════════════════════════════════════════════════════════════
# 6. Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Build Sentinel training data from multiple local raw sources."
    )
    parser.add_argument(
        "--manifest",
        default="ml-service/scripts/dataset_manifest.json",
        help="Path to dataset manifest JSON.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Sentinel Multi-Source Training Data Builder")
    print("=" * 60)

    # 1. Load manifest
    manifest_path = Path(args.manifest)
    cfg = load_manifest(manifest_path)
    fusion_mode = cfg.get("fusion_mode", "sum")
    synthetic_fallback = cfg.get("synthetic_fallback", True)
    synthetic_seed = cfg.get("synthetic_seed", 42)

    # 2. Ingest sources
    try:
        frames, contributions = ingest_sources(cfg)
    except RuntimeError as e:
        if synthetic_fallback:
            frames, contributions = [], {}
        else:
            raise

    # 3. Synthetic fallback if no real data loaded
    if not frames:
        if synthetic_fallback:
            syn = generate_synthetic(seed=synthetic_seed)
            frames = [syn]
            contributions["synthetic"] = len(syn)
        else:
            raise RuntimeError("No usable sources and synthetic_fallback is disabled.")

    # 4. Fuse sources
    print(f"\n  Fusing {len(frames)} source(s) using mode='{fusion_mode}'")
    fused = fuse_sources(frames, mode=fusion_mode)
    print(f"  Fused series: {len(fused)} rows")

    if fused.empty:
        raise RuntimeError("Fused dataset is empty.")

    # 5. Feature engineering
    featured = build_features(fused.copy())

    # Ensure all 26 columns present
    for col in FEATURE_COLS:
        if col not in featured.columns:
            featured[col] = 0.0

    # 6. Final output
    out_cols = FEATURE_COLS + ["future_req_rate_5m", "is_surge"]
    out = featured[out_cols].astype(np.float32)

    output_path = Path(cfg.get("output_path", "ml-service/data/processed/training_data.parquet"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output_path)

    print(f"\n  ✓ Saved training data: {output_path} ({len(out)} rows)")

    # 7. Quality report
    report_path = Path(cfg.get(
        "quality_report_path",
        "ml-service/data/processed/dataset_quality_report.json",
    ))
    report = generate_quality_report(
        df=fused,
        source_contributions=contributions,
        output_path=report_path,
    )

    # 8. Summary
    print(f"\n{'='*60}")
    print(f"  BUILD COMPLETE")
    print(f"  Rows:     {len(out)}")
    print(f"  Features: {len(FEATURE_COLS)}")
    print(f"  Sources:  {', '.join(contributions.keys())}")
    print(f"  Fusion:   {fusion_mode}")
    print(f"  Output:   {output_path}")
    print(f"  Report:   {report_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
