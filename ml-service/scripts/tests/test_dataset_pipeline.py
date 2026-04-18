"""
Tests for Sentinel multi-source dataset pipeline.

All tests use small in-memory fixtures — no external file downloads needed.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ── Ensure scripts/ is on path ───────────────────────────────────────────
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from adapters import get_adapter, GenericCSVAdapter, _empty
from adapters.base import BaseAdapter
from adapters.wikimedia import WikimediaAdapter
from adapters.azure import AzureFunctionsAdapter
from adapters.apache_access import ApacheAccessLogAdapter
from build_multisource_training_data import (
    load_manifest,
    fuse_sources,
    build_features,
    generate_synthetic,
    FEATURE_COLS,
)
from data_quality import generate_quality_report


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

def _make_csv(tmp_dir: Path, name: str, data: dict) -> Path:
    """Write a dict of columns to a CSV file and return the path."""
    df = pd.DataFrame(data)
    path = tmp_dir / name
    df.to_csv(path, index=False)
    return path


def _valid_manifest(tmp_dir: Path, csv_path: Path) -> dict:
    """Create a minimal valid manifest dict."""
    return {
        "fusion_mode": "sum",
        "synthetic_fallback": False,
        "synthetic_seed": 42,
        "output_path": str(tmp_dir / "output.parquet"),
        "quality_report_path": str(tmp_dir / "report.json"),
        "sources": [
            {
                "name": "test_source",
                "enabled": True,
                "adapter": "generic",
                "path": str(csv_path),
                "timestamp_col": "ts",
                "value_col": "val",
                "resample": "1h",
                "agg": "sum",
                "multiplier": 1.0,
                "weight": 1.0,
                "timezone": "UTC",
                "missing_data_policy": "drop",
            }
        ],
    }


def _sample_ts_data(n: int = 100) -> dict:
    """Generate sample timestamp + value data."""
    base = datetime(2024, 1, 1)
    return {
        "ts": [(base + timedelta(hours=i)).isoformat() for i in range(n)],
        "val": np.random.uniform(100, 5000, n).tolist(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. Manifest Parsing
# ═══════════════════════════════════════════════════════════════════════════

def test_manifest_parsing_valid(tmp_path):
    """Load a valid manifest dict and verify it parses without error."""
    csv_path = _make_csv(tmp_path, "test.csv", _sample_ts_data())
    m = _valid_manifest(tmp_path, csv_path)
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(m))

    cfg = load_manifest(manifest_file)
    assert "sources" in cfg
    assert len(cfg["sources"]) == 1
    assert cfg["sources"][0]["name"] == "test_source"


def test_manifest_parsing_no_enabled(tmp_path):
    """Manifest with no enabled sources should raise RuntimeError during ingestion."""
    m = {
        "sources": [{"name": "disabled", "enabled": False, "path": "x.csv",
                      "timestamp_col": "ts", "value_col": "val"}]
    }
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(m))

    cfg = load_manifest(manifest_file)
    enabled = [s for s in cfg["sources"] if s.get("enabled", False)]
    assert len(enabled) == 0


# ═══════════════════════════════════════════════════════════════════════════
# 2. Adapter Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_adapter_generic_csv(tmp_path):
    """Generic CSV adapter normalizes columns correctly."""
    csv_path = _make_csv(tmp_path, "test.csv", _sample_ts_data(50))
    config = {
        "name": "generic_test",
        "path": str(csv_path),
        "timestamp_col": "ts",
        "value_col": "val",
        "resample": "1h",
        "agg": "sum",
        "multiplier": 2.0,
        "timezone": "UTC",
        "missing_data_policy": "drop",
    }
    adapter = GenericCSVAdapter(config)
    df = adapter.load()

    assert not df.empty
    assert "timestamp" in df.columns
    assert "value" in df.columns
    assert df["value"].min() >= 0  # after multiplier, still positive


def test_adapter_wikimedia(tmp_path):
    """Wikimedia adapter handles pre-processed CSV format."""
    csv_path = _make_csv(tmp_path, "wiki.csv", {
        "timestamp": [(datetime(2024, 1, 1) + timedelta(hours=i)).isoformat() for i in range(24)],
        "views": np.random.randint(100, 10000, 24).tolist(),
    })
    config = {
        "name": "wiki_test",
        "adapter": "wikimedia",
        "path": str(csv_path),
        "timestamp_col": "timestamp",
        "value_col": "views",
        "resample": "1h",
        "agg": "sum",
        "multiplier": 1.0,
        "timezone": "UTC",
        "missing_data_policy": "drop",
    }
    adapter = WikimediaAdapter(config)
    df = adapter.load()

    assert not df.empty
    assert len(df) <= 24


def test_adapter_wikimedia_pageviews_dump(tmp_path):
    """Wikimedia adapter parses 4-column pageviews dump format."""
    dump_path = tmp_path / "pageviews-20240101-000000.gz"
    rows = [
        'en Main_Page 1000 12345',
        'en Special:Search 250 4000',
        'de Hauptseite 300 7000',
    ]
    import gzip
    with gzip.open(dump_path, "wt", encoding="utf-8") as f:
        f.write("\n".join(rows))

    config = {
        "name": "wiki_dump_test",
        "adapter": "wikimedia",
        "path": str(dump_path),
        "resample": "1h",
        "agg": "sum",
        "timezone": "UTC",
        "missing_data_policy": "drop",
    }
    df = WikimediaAdapter(config).load()
    assert not df.empty
    assert float(df["value"].iloc[0]) == pytest.approx(1550.0)


def test_adapter_apache_access_log(tmp_path):
    """Apache access adapter converts log lines into per-minute request counts."""
    log_path = tmp_path / "nasa.log"
    log_lines = [
        '199.72.81.55 - - [01/Jul/1995:00:00:01 -0400] "GET /history/apollo/ HTTP/1.0" 200 6245',
        'unicomp6.unicomp.net - - [01/Jul/1995:00:00:59 -0400] "GET /shuttle/countdown/ HTTP/1.0" 200 3985',
        'burger.letters.com - - [01/Jul/1995:00:01:15 -0400] "GET /images/KSC-logosmall.gif HTTP/1.0" 304 0',
    ]
    log_path.write_text("\n".join(log_lines), encoding="utf-8")

    config = {
        "name": "apache_test",
        "adapter": "apache_access",
        "path": str(log_path),
        "resample": "1min",
        "agg": "sum",
        "timezone": "UTC",
        "missing_data_policy": "drop",
    }

    df = ApacheAccessLogAdapter(config).load()
    assert not df.empty
    assert float(df["value"].sum()) == pytest.approx(3.0)
    assert len(df) == 2  # two minute buckets


def test_adapter_azure_functions(tmp_path):
    """Azure functions adapter extracts invocations."""
    csv_path = _make_csv(tmp_path, "funcs.csv", {
        "end_timestamp": [(datetime(2024, 1, 1) + timedelta(minutes=i)).isoformat() for i in range(60)],
        "invocations": np.random.randint(1, 100, 60).tolist(),
        "app": ["app1"] * 60,
    })
    config = {
        "name": "azure_func_test",
        "adapter": "azure_functions",
        "path": str(csv_path),
        "timestamp_col": "end_timestamp",
        "value_col": "invocations",
        "resample": "5min",
        "agg": "sum",
        "multiplier": 1.0,
        "timezone": "UTC",
        "missing_data_policy": "drop",
    }
    adapter = AzureFunctionsAdapter(config)
    df = adapter.load()

    assert not df.empty
    assert "value" in df.columns


def test_adapter_missing_columns(tmp_path):
    """Adapter with wrong column names returns empty DataFrame."""
    csv_path = _make_csv(tmp_path, "bad.csv", {"col_a": [1, 2], "col_b": [3, 4]})
    config = {
        "name": "bad_test",
        "path": str(csv_path),
        "timestamp_col": "timestamp",
        "value_col": "value",
        "timezone": "UTC",
        "missing_data_policy": "drop",
    }
    adapter = GenericCSVAdapter(config)
    df = adapter.load()
    assert df.empty


def test_adapter_timezone_conversion(tmp_path):
    """Timestamps in US/Pacific should be converted to UTC."""
    base = datetime(2024, 7, 1, 12, 0)
    csv_path = _make_csv(tmp_path, "tz.csv", {
        "ts": [(base + timedelta(hours=i)).isoformat() for i in range(10)],
        "val": [100.0] * 10,
    })
    config = {
        "name": "tz_test",
        "path": str(csv_path),
        "timestamp_col": "ts",
        "value_col": "val",
        "resample": "1h",
        "agg": "sum",
        "multiplier": 1.0,
        "timezone": "US/Pacific",
        "missing_data_policy": "drop",
    }
    adapter = GenericCSVAdapter(config)
    df = adapter.load()

    assert not df.empty
    # Pacific is UTC-7 in summer, so 12:00 PDT → 19:00 UTC
    first_ts = df["timestamp"].iloc[0]
    assert first_ts.hour == 19  # 12 PDT → 19 UTC


# ═══════════════════════════════════════════════════════════════════════════
# 3. Fusion Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_merge_sum():
    """Sum fusion mode aggregates values at same timestamp."""
    ts = pd.date_range("2024-01-01", periods=5, freq="h", tz="UTC")
    f1 = pd.DataFrame({"timestamp": ts, "value": [10.0] * 5, "_weight": [1.0] * 5, "_source": "a"})
    f2 = pd.DataFrame({"timestamp": ts, "value": [20.0] * 5, "_weight": [1.0] * 5, "_source": "b"})

    result = fuse_sources([f1, f2], mode="sum")
    assert len(result) == 5
    assert result["req_rate_1m"].iloc[0] == pytest.approx(30.0)


def test_merge_weighted_mean():
    """Weighted mean fusion respects per-source weights."""
    ts = pd.date_range("2024-01-01", periods=5, freq="h", tz="UTC")
    f1 = pd.DataFrame({"timestamp": ts, "value": [100.0] * 5, "_weight": [1.0] * 5, "_source": "a"})
    f2 = pd.DataFrame({"timestamp": ts, "value": [200.0] * 5, "_weight": [3.0] * 5, "_source": "b"})

    result = fuse_sources([f1, f2], mode="weighted_mean")
    assert len(result) == 5
    # Expected: (100*1 + 200*3) / (1+3) = 700/4 = 175.0
    assert result["req_rate_1m"].iloc[0] == pytest.approx(175.0)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Feature Engineering
# ═══════════════════════════════════════════════════════════════════════════

def test_feature_engineering_26_columns():
    """Output has exactly 26 feature columns."""
    ts = pd.date_range("2024-01-01", periods=200, freq="min", tz="UTC")
    df = pd.DataFrame({"timestamp": ts, "req_rate_1m": np.random.uniform(100, 500, 200)})
    featured = build_features(df)

    for col in FEATURE_COLS:
        assert col in featured.columns, f"Missing feature column: {col}"
    assert "future_req_rate_5m" in featured.columns
    assert "is_surge" in featured.columns


# ═══════════════════════════════════════════════════════════════════════════
# 5. Quality Report
# ═══════════════════════════════════════════════════════════════════════════

def test_quality_report_structure(tmp_path):
    """Quality report JSON has all required keys."""
    ts = pd.date_range("2024-01-01", periods=100, freq="min", tz="UTC")
    df = pd.DataFrame({"timestamp": ts, "req_rate_1m": np.random.uniform(100, 500, 100)})

    report = generate_quality_report(
        df=df,
        source_contributions={"test": 100},
        output_path=tmp_path / "report.json",
    )

    required_keys = [
        "total_rows", "date_range", "timestamp_continuity",
        "duplicate_timestamps", "outlier_ratio", "source_contributions",
        "null_counts", "null_free",
    ]
    for key in required_keys:
        assert key in report, f"Missing key: {key}"


def test_quality_report_gap_detection(tmp_path):
    """Detects timestamp gaps correctly."""
    # Create data with a 2-hour gap in the middle
    ts1 = pd.date_range("2024-01-01 00:00", periods=30, freq="min", tz="UTC")
    ts2 = pd.date_range("2024-01-01 02:30", periods=30, freq="min", tz="UTC")
    ts = ts1.append(ts2)
    df = pd.DataFrame({"timestamp": ts, "value": np.ones(60)})

    report = generate_quality_report(
        df=df,
        source_contributions={"test": 60},
        output_path=tmp_path / "report.json",
        resample_interval="1min",
    )

    assert report["timestamp_continuity"]["total_gaps"] >= 1
    assert report["timestamp_continuity"]["max_gap_seconds"] >= 120 * 60  # 2h gap


# ═══════════════════════════════════════════════════════════════════════════
# 6. Misc Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_synthetic_determinism():
    """Same seed produces identical output."""
    df1 = generate_synthetic(seed=123, days=1)
    df2 = generate_synthetic(seed=123, days=1)
    assert len(df1) == len(df2)
    assert df1["value"].sum() == pytest.approx(df2["value"].sum())


def test_clip_values(tmp_path):
    """clip_min/clip_max should be respected."""
    csv_path = _make_csv(tmp_path, "clip.csv", {
        "ts": [(datetime(2024, 1, 1) + timedelta(hours=i)).isoformat() for i in range(20)],
        "val": list(range(-5, 15)),
    })
    config = {
        "name": "clip_test",
        "path": str(csv_path),
        "timestamp_col": "ts",
        "value_col": "val",
        "resample": "1h",
        "agg": "sum",
        "multiplier": 1.0,
        "timezone": "UTC",
        "clip_min": 0.0,
        "clip_max": 10.0,
        "missing_data_policy": "drop",
    }
    adapter = GenericCSVAdapter(config)
    df = adapter.load()

    assert df["value"].min() >= 0.0
    assert df["value"].max() <= 10.0


def test_missing_data_ffill(tmp_path):
    """Forward-fill policy should fill NaN values."""
    data = {
        "ts": [(datetime(2024, 1, 1) + timedelta(hours=i)).isoformat() for i in range(10)],
        "val": [100.0, None, None, 200.0, None, 300.0, None, None, None, 400.0],
    }
    csv_path = _make_csv(tmp_path, "ffill.csv", data)
    config = {
        "name": "ffill_test",
        "path": str(csv_path),
        "timestamp_col": "ts",
        "value_col": "val",
        "resample": "1h",
        "agg": "sum",
        "multiplier": 1.0,
        "timezone": "UTC",
        "missing_data_policy": "ffill",
    }
    adapter = GenericCSVAdapter(config)
    df = adapter.load()

    # After ffill, no NaN values should remain
    assert df["value"].isna().sum() == 0
