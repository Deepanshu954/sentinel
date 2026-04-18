"""
Google ClusterData 2019 adapter for Sentinel.

Handles the Borg cluster trace format. Supports both:
1. Full ClusterData 2019 instance_usage tables (start_time, end_time, avg_cpu, avg_mem)
2. Kaggle mirror/sample CSVs with similar schemas
"""

from __future__ import annotations

import pandas as pd

from .base import BaseAdapter, _empty


class GoogleClusterAdapter(BaseAdapter):
    """Adapter for Google ClusterData 2019 (Borg traces)."""

    def _read_raw(self) -> pd.DataFrame:
        ts_col = self.config.get("timestamp_col", "start_time")
        val_col = self.config.get("value_col", "avg_cpu")

        try:
            raw = pd.read_csv(self.path)
        except Exception as e:
            print(f"  SKIP [{self.name}] read error: {e}")
            return _empty()

        if ts_col not in raw.columns or val_col not in raw.columns:
            # Try common Google cluster column variations
            alt_ts = ["start_time", "start", "timestamp", "time", "start_time_us"]
            alt_val = ["avg_cpu", "average_usage.cpus", "cpu_usage", "mean_cpu_usage_rate"]
            ts_col = next((c for c in alt_ts if c in raw.columns), ts_col)
            val_col = next((c for c in alt_val if c in raw.columns), val_col)

        if ts_col not in raw.columns or val_col not in raw.columns:
            print(f"  SKIP [{self.name}] missing columns: need {ts_col}, {val_col}")
            return _empty()

        out = raw[[ts_col, val_col]].copy()

        # Google traces use microsecond timestamps — detect and convert
        sample = pd.to_numeric(out[ts_col], errors="coerce").dropna()
        if len(sample) > 0 and sample.iloc[0] > 1e15:
            # Microsecond epoch
            out["timestamp"] = pd.to_datetime(
                pd.to_numeric(out[ts_col], errors="coerce"), unit="us", utc=True
            )
        elif len(sample) > 0 and sample.iloc[0] > 1e12:
            # Millisecond epoch
            out["timestamp"] = pd.to_datetime(
                pd.to_numeric(out[ts_col], errors="coerce"), unit="ms", utc=True
            )
        elif len(sample) > 0 and sample.iloc[0] > 1e9:
            # Second epoch
            out["timestamp"] = pd.to_datetime(
                pd.to_numeric(out[ts_col], errors="coerce"), unit="s", utc=True
            )
        else:
            # String datetime
            out["timestamp"] = pd.to_datetime(out[ts_col], errors="coerce", utc=True)

        out["value"] = pd.to_numeric(out[val_col], errors="coerce")
        return out[["timestamp", "value"]]
