"""
Apache access-log adapter for Sentinel.

Parses Common/Combined access logs (plain text or .gz) and emits a
timestamp/value time series where value = requests per log line.

This adapter is useful for:
- NASA HTTP 1995 logs (Internet Traffic Archive)
- General web server traffic logs in CLF-like format
"""

from __future__ import annotations

import gzip
import re
from collections import defaultdict
from datetime import datetime

import pandas as pd

from .base import BaseAdapter, _empty

# Apache/NCSA timestamp format: [01/Jul/1995:00:00:01 -0400]
LOG_TS_RE = re.compile(r"\[(?P<ts>[^\]]+)\]")
LOG_TS_FORMAT = "%d/%b/%Y:%H:%M:%S %z"


class ApacheAccessLogAdapter(BaseAdapter):
    """Adapter for Apache access logs (plain or gzip)."""

    def _read_raw(self) -> pd.DataFrame:
        open_fn = gzip.open if self.path.suffix.lower() == ".gz" else open
        counts: dict[pd.Timestamp, int] = defaultdict(int)

        try:
            with open_fn(self.path, "rt", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    match = LOG_TS_RE.search(line)
                    if not match:
                        continue

                    raw_ts = match.group("ts")
                    try:
                        dt = datetime.strptime(raw_ts, LOG_TS_FORMAT)
                    except ValueError:
                        continue

                    # Aggregate directly at minute granularity to keep memory stable
                    minute_ts = pd.Timestamp(dt).tz_convert("UTC").floor("min")
                    counts[minute_ts] += 1
        except Exception as exc:
            print(f"  SKIP [{self.name}] apache log parse error: {exc}")
            return _empty()

        if not counts:
            print(f"  SKIP [{self.name}] no parseable Apache log timestamps found")
            return _empty()

        out = pd.DataFrame(
            {
                "timestamp": list(counts.keys()),
                "value": list(counts.values()),
            }
        ).sort_values("timestamp")

        return out.reset_index(drop=True)
