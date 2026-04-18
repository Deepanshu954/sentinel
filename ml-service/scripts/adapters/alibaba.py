"""
Alibaba Cluster Trace adapter for Sentinel.

Supports:
1. **v2018** — machine_usage: machine_id, time_stamp, cpu_util_percent, mem_util_percent
2. **v2026-GenAI** — request traces with latency + request_count columns
"""

from __future__ import annotations

import pandas as pd

from .base import BaseAdapter, _empty


class AlibabaClusterAdapter(BaseAdapter):
    """Adapter for Alibaba Cluster Trace Program data."""

    def _read_raw(self) -> pd.DataFrame:
        ts_col = self.config.get("timestamp_col", "time_stamp")
        val_col = self.config.get("value_col", "cpu_util_percent")

        try:
            raw = pd.read_csv(self.path)
        except Exception as e:
            print(f"  SKIP [{self.name}] read error: {e}")
            return _empty()

        if ts_col not in raw.columns or val_col not in raw.columns:
            # Try common Alibaba column variations
            alt_ts = ["time_stamp", "timestamp", "ts", "start_time", "time"]
            alt_val = [
                "cpu_util_percent", "request_count", "cpu_usage",
                "mem_util_percent", "latency",
            ]
            ts_col = next((c for c in alt_ts if c in raw.columns), ts_col)
            val_col = next((c for c in alt_val if c in raw.columns), val_col)

        if ts_col not in raw.columns or val_col not in raw.columns:
            print(f"  SKIP [{self.name}] missing columns: need {ts_col}, {val_col}")
            return _empty()

        out = raw[[ts_col, val_col]].copy()

        # Alibaba v2018 uses integer second-epoch timestamps
        sample = pd.to_numeric(out[ts_col], errors="coerce").dropna()
        if len(sample) > 0 and sample.iloc[0] > 1e9:
            out["timestamp"] = pd.to_datetime(
                pd.to_numeric(out[ts_col], errors="coerce"), unit="s", utc=True
            )
        else:
            out["timestamp"] = pd.to_datetime(out[ts_col], errors="coerce", utc=True)

        out["value"] = pd.to_numeric(out[val_col], errors="coerce")
        return out[["timestamp", "value"]]
