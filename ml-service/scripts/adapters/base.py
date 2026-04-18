"""
Base adapter interface for Sentinel dataset ingestion.

Every concrete adapter extends BaseAdapter and implements `load()`,
which returns a two-column DataFrame: timestamp (UTC datetime64) + value (float64).
"""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


class BaseAdapter(abc.ABC):
    """Abstract base for all dataset adapters."""

    def __init__(self, source_config: Dict[str, Any]):
        self.name: str = source_config["name"]
        self.path: Path = Path(source_config["path"])
        self.config = source_config

        # Optional enrichment fields
        self.timezone: str = source_config.get("timezone", "UTC")
        self.filter_start: Optional[str] = source_config.get("filter_start")
        self.filter_end: Optional[str] = source_config.get("filter_end")
        self.clip_min: Optional[float] = source_config.get("clip_min")
        self.clip_max: Optional[float] = source_config.get("clip_max")
        self.missing_data_policy: str = source_config.get("missing_data_policy", "drop")
        self.resample: str = source_config.get("resample", "1min")
        self.agg: str = source_config.get("agg", "sum")
        self.multiplier: float = float(source_config.get("multiplier", 1.0))
        self.weight: float = float(source_config.get("weight", 1.0))

    # ── public entry point ──────────────────────────────────────────────

    def load(self) -> pd.DataFrame:
        """Load, normalise, and return (timestamp, value) DataFrame."""
        if not self.path.exists():
            print(f"  SKIP [{self.name}] file not found: {self.path}")
            return _empty()

        raw = self._read_raw()
        if raw.empty:
            return _empty()

        df = self._normalise(raw)
        df = self._apply_timezone(df)
        df = self._apply_filters(df)
        df = self._resample_and_agg(df)
        df = self._apply_multiplier(df)
        df = self._apply_clip(df)
        df = self._handle_missing(df)

        print(f"  LOAD [{self.name}] rows={len(df)}")
        return df

    # ── abstract: subclasses must implement ──────────────────────────────

    @abc.abstractmethod
    def _read_raw(self) -> pd.DataFrame:
        """Read the raw file and return a DataFrame with at least
        'timestamp' (parseable) and 'value' (numeric) columns."""
        ...

    # ── shared post-processing steps ─────────────────────────────────────

    def _normalise(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure columns are exactly [timestamp, value] with correct dtypes."""
        if "timestamp" not in df.columns or "value" not in df.columns:
            print(f"  SKIP [{self.name}] missing required columns after adapter read")
            return _empty()

        out = df[["timestamp", "value"]].copy()
        out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
        out["value"] = pd.to_numeric(out["value"], errors="coerce")
        out = out.dropna(subset=["timestamp", "value"])
        return out

    def _apply_timezone(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        ts = df["timestamp"]
        if ts.dt.tz is None:
            df["timestamp"] = ts.dt.tz_localize(self.timezone).dt.tz_convert("UTC")
        else:
            df["timestamp"] = ts.dt.tz_convert("UTC")
        return df

    def _apply_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        if self.filter_start:
            start = pd.Timestamp(self.filter_start, tz="UTC")
            df = df[df["timestamp"] >= start]
        if self.filter_end:
            end = pd.Timestamp(self.filter_end, tz="UTC")
            df = df[df["timestamp"] <= end]
        return df

    def _resample_and_agg(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.set_index("timestamp")
        agg_map = {"mean": "mean", "max": "max", "sum": "sum", "min": "min"}
        func = agg_map.get(self.agg, "sum")
        df = df.resample(self.resample).agg(func)
        df = df.reset_index()
        return df

    def _apply_multiplier(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or self.multiplier == 1.0:
            return df
        df["value"] = df["value"] * self.multiplier
        return df

    def _apply_clip(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        lower = self.clip_min if self.clip_min is not None else None
        upper = self.clip_max if self.clip_max is not None else None
        if lower is not None or upper is not None:
            df["value"] = df["value"].clip(lower=lower, upper=upper)
        return df

    def _handle_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        policy = self.missing_data_policy
        if policy == "drop":
            df = df.dropna(subset=["value"])
        elif policy == "zero":
            df["value"] = df["value"].fillna(0.0)
        elif policy == "ffill":
            df["value"] = df["value"].ffill().bfill()
        elif policy == "interpolate":
            df["value"] = df["value"].interpolate(method="linear").bfill().ffill()
        else:
            df = df.dropna(subset=["value"])
        return df


class GenericCSVAdapter(BaseAdapter):
    """Fallback adapter for any CSV/Parquet file with configurable column names."""

    def _read_raw(self) -> pd.DataFrame:
        ts_col = self.config.get("timestamp_col", "timestamp")
        val_col = self.config.get("value_col", "value")

        suffix = self.path.suffix.lower()
        if suffix == ".parquet":
            raw = pd.read_parquet(self.path)
        elif suffix in (".csv", ".tsv", ".txt"):
            sep = "\t" if suffix == ".tsv" else ","
            raw = pd.read_csv(self.path, sep=sep)
        else:
            print(f"  SKIP [{self.name}] unsupported format: {suffix}")
            return _empty()

        if ts_col not in raw.columns or val_col not in raw.columns:
            print(f"  SKIP [{self.name}] missing columns: need {ts_col}, {val_col}")
            return _empty()

        return raw.rename(columns={ts_col: "timestamp", val_col: "value"})


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=["timestamp", "value"])
