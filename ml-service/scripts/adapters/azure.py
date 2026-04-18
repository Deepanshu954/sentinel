"""
Azure dataset adapters for Sentinel.

Supports two Azure public dataset families:
1. **Azure Functions 2019** — minute-level invocation traces
   Schema: app, func, end_timestamp, duration, invocations
2. **Azure VM V2 2019** — CPU utilization readings
   Schema: vmid, timestamp_vm, min_cpu, max_cpu, avg_cpu
"""

from __future__ import annotations

import pandas as pd

from .base import BaseAdapter, _empty


class AzureFunctionsAdapter(BaseAdapter):
    """Adapter for Azure Functions 2019 invocation traces."""

    def _read_raw(self) -> pd.DataFrame:
        ts_col = self.config.get("timestamp_col", "end_timestamp")
        val_col = self.config.get("value_col", "invocations")

        raw = pd.read_csv(self.path)

        if ts_col not in raw.columns or val_col not in raw.columns:
            # Try common alternative column names
            alt_ts = ["end_timestamp", "timestamp", "Timestamp", "time"]
            alt_val = ["invocations", "Invocations", "count", "Count"]
            ts_col = next((c for c in alt_ts if c in raw.columns), ts_col)
            val_col = next((c for c in alt_val if c in raw.columns), val_col)

        if ts_col not in raw.columns or val_col not in raw.columns:
            print(f"  SKIP [{self.name}] missing columns: need {ts_col}, {val_col}")
            return _empty()

        return raw.rename(columns={ts_col: "timestamp", val_col: "value"})


class AzureVMAdapter(BaseAdapter):
    """Adapter for Azure VM V2 2019 CPU utilization traces."""

    def _read_raw(self) -> pd.DataFrame:
        ts_col = self.config.get("timestamp_col", "timestamp_vm")
        val_col = self.config.get("value_col", "avg_cpu")

        raw = pd.read_csv(self.path)

        if ts_col not in raw.columns or val_col not in raw.columns:
            alt_ts = ["timestamp_vm", "timestamp", "Timestamp", "time"]
            alt_val = ["avg_cpu", "max_cpu", "cpu_utilization", "vm_utilization"]
            ts_col = next((c for c in alt_ts if c in raw.columns), ts_col)
            val_col = next((c for c in alt_val if c in raw.columns), val_col)

        if ts_col not in raw.columns or val_col not in raw.columns:
            print(f"  SKIP [{self.name}] missing columns: need {ts_col}, {val_col}")
            return _empty()

        return raw.rename(columns={ts_col: "timestamp", val_col: "value"})
