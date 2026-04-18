"""
Wikimedia pageview adapter for Sentinel.

Handles two common Wikimedia formats:
1. **Pageview-complete hourly** — space-delimited: `domain-code page-title [mobile|desktop] hourly-views ...`
2. **Pre-processed CSV** — columns: timestamp, views (already aggregated)

For format (1), the adapter sums all pages/domains per hour into a single global traffic signal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd

from .base import BaseAdapter, _empty


class WikimediaAdapter(BaseAdapter):
    """Adapter for Wikimedia pageview data (global aggregation)."""

    def _read_raw(self) -> pd.DataFrame:
        suffix = self.path.suffix.lower()

        # Pre-processed CSV with timestamp + views columns
        if suffix == ".csv":
            return self._read_csv()

        # Raw pageview-complete hourly dumps (space-delimited, gzipped or plain)
        if suffix in (".gz", ".txt"):
            return self._read_pageview_dump()

        # Parquet (pre-processed)
        if suffix == ".parquet":
            raw = pd.read_parquet(self.path)
            ts_col = self.config.get("timestamp_col", "timestamp")
            val_col = self.config.get("value_col", "views")
            if ts_col in raw.columns and val_col in raw.columns:
                return raw.rename(columns={ts_col: "timestamp", val_col: "value"})
            return _empty()

        print(f"  SKIP [{self.name}] unsupported wiki format: {suffix}")
        return _empty()

    def _read_csv(self) -> pd.DataFrame:
        ts_col = self.config.get("timestamp_col", "timestamp")
        val_col = self.config.get("value_col", "views")

        raw = pd.read_csv(self.path)
        if ts_col not in raw.columns or val_col not in raw.columns:
            print(f"  SKIP [{self.name}] CSV missing columns: need {ts_col}, {val_col}")
            return _empty()

        return raw.rename(columns={ts_col: "timestamp", val_col: "value"})

    def _read_pageview_dump(self) -> pd.DataFrame:
        """Parse Wikimedia hourly dump format.

        Supports both common variants:
        1. `project page views bytes` (4-column pageviews dump)
        2. `project page access hourly daily` (5-column pageview-complete)

        File name usually encodes the hour: `pageviews-YYYYMMDD-HH0000.gz`
        """
        try:
            compression = "gzip" if self.path.suffix == ".gz" else None
            raw = pd.read_csv(
                self.path,
                sep=" ",
                header=None,
                compression=compression,
                on_bad_lines="skip",
            )

            if raw.empty:
                return _empty()

            # Normalize both formats to a single numeric "views" column.
            if raw.shape[1] >= 5:
                # pageview-complete style: [project, page, access, hourly, daily]
                views_col = 3
            elif raw.shape[1] >= 3:
                # pageviews style: [project, page, views, bytes]
                views_col = 2
            else:
                print(f"  SKIP [{self.name}] unsupported Wikimedia dump column count: {raw.shape[1]}")
                return _empty()

            # Extract timestamp from filename (pageviews-YYYYMMDD-HH0000.gz)
            stem = self.path.stem.replace(".gz", "").replace("pageviews-", "")
            parts = stem.split("-")
            if len(parts) >= 2:
                ts_str = f"{parts[0][:8]}T{parts[1][:2]}:00:00"
                ts = pd.Timestamp(ts_str)
            else:
                ts = pd.Timestamp("2024-01-01")

            total_views = pd.to_numeric(raw.iloc[:, views_col], errors="coerce").sum()
            return pd.DataFrame({"timestamp": [ts], "value": [total_views]})

        except Exception as e:
            print(f"  SKIP [{self.name}] pageview dump parse error: {e}")
            return _empty()
