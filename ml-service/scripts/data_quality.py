"""
Dataset quality checks for Sentinel training data.

Generates a JSON report covering timestamp continuity, duplicates,
outliers, source contributions, and null counts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def generate_quality_report(
    df: pd.DataFrame,
    source_contributions: Dict[str, int],
    output_path: Path,
    resample_interval: str = "1min",
) -> Dict[str, Any]:
    """Analyse training data quality and write report JSON.

    Parameters
    ----------
    df : DataFrame with at least a 'timestamp' or DatetimeIndex and numeric columns.
    source_contributions : {source_name: row_count} from ingestion.
    output_path : where to save the JSON report.
    resample_interval : expected time gap between consecutive rows.

    Returns
    -------
    The report dict (also written to output_path).
    """
    report: Dict[str, Any] = {}

    # ── Basic stats ──────────────────────────────────────────────────────
    report["total_rows"] = int(len(df))
    report["total_columns"] = int(len(df.columns))

    # Resolve timestamp column
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"], errors="coerce")
    elif isinstance(df.index, pd.DatetimeIndex):
        ts = df.index.to_series()
    else:
        ts = pd.Series(dtype="datetime64[ns]")

    if not ts.empty:
        report["date_range"] = {
            "start": str(ts.min()),
            "end": str(ts.max()),
            "span_days": round((ts.max() - ts.min()).total_seconds() / 86400, 2),
        }
    else:
        report["date_range"] = {"start": None, "end": None, "span_days": 0}

    # ── Timestamp continuity / gaps ──────────────────────────────────────
    gaps = _detect_gaps(ts, resample_interval)
    report["timestamp_continuity"] = {
        "total_gaps": len(gaps),
        "max_gap_seconds": float(max(g["gap_seconds"] for g in gaps)) if gaps else 0,
        "gaps": gaps[:20],  # Cap at 20 to keep report readable
    }

    # ── Duplicate timestamps ─────────────────────────────────────────────
    dup_count = int(ts.duplicated().sum()) if not ts.empty else 0
    report["duplicate_timestamps"] = dup_count

    # ── Outlier ratio ────────────────────────────────────────────────────
    if "req_rate_1m" in df.columns:
        report["outlier_ratio"] = _outlier_ratio(df["req_rate_1m"])
    elif "value" in df.columns:
        report["outlier_ratio"] = _outlier_ratio(df["value"])
    else:
        report["outlier_ratio"] = 0.0

    # ── Source contributions ─────────────────────────────────────────────
    total_contributed = sum(source_contributions.values()) or 1
    report["source_contributions"] = {
        name: {
            "rows": count,
            "percent": round(100.0 * count / total_contributed, 2),
        }
        for name, count in source_contributions.items()
    }

    # ── Per-column null counts ───────────────────────────────────────────
    nulls = df.isnull().sum()
    report["null_counts"] = {
        col: int(nulls[col]) for col in df.columns if nulls[col] > 0
    }
    report["null_free"] = int(nulls.sum()) == 0

    # ── Write report ─────────────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"  Quality report saved to {output_path}")
    return report


def _detect_gaps(
    ts: pd.Series, expected_interval: str
) -> List[Dict[str, Any]]:
    """Find gaps larger than 2× the expected resample interval."""
    if ts.empty or len(ts) < 2:
        return []

    ts_sorted = ts.sort_values().reset_index(drop=True)
    diffs = ts_sorted.diff().dropna()

    expected = pd.Timedelta(expected_interval)
    threshold = expected * 2

    gaps = []
    for idx, delta in diffs.items():
        if delta > threshold:
            gaps.append({
                "after": str(ts_sorted.iloc[idx - 1]),
                "before": str(ts_sorted.iloc[idx]),
                "gap_seconds": round(delta.total_seconds(), 1),
            })

    return gaps


def _outlier_ratio(series: pd.Series, window: int = 60, sigma: float = 3.0) -> float:
    """Fraction of values > 3σ from the rolling median."""
    if series.empty or len(series) < window:
        return 0.0

    median = series.rolling(window, min_periods=1).median()
    std = series.rolling(window, min_periods=1).std().fillna(1.0)
    z_scores = ((series - median) / std.clip(lower=1e-6)).abs()
    outliers = (z_scores > sigma).sum()
    return round(float(outliers) / len(series), 6)
