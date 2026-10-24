"""Time helpers. Internally every timestamp is float seconds since the Unix epoch (UTC)."""

from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

DAY = 86_400.0
HOUR = 3_600.0


def epoch(d: date) -> float:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()


def add_months(ts: float, months: int) -> float:
    """Same day-of-month `months` later (clamped to month end), keeping the time of day."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    m = dt.month - 1 + months
    year, month = dt.year + m // 12, m % 12 + 1
    last_day = (datetime(year + month // 12, month % 12 + 1, 1, tzinfo=timezone.utc)
                - datetime(year, month, 1, tzinfo=timezone.utc)).days
    return dt.replace(year=year, month=month, day=min(dt.day, last_day)).timestamp()


def to_iso(ts) -> np.ndarray:
    """Seconds -> 'YYYY-MM-DD HH:MM:SS' strings; NaN -> None."""
    arr = np.asarray(ts, dtype="float64")
    out = np.full(arr.shape, None, dtype=object)
    ok = ~np.isnan(arr)
    s = np.datetime_as_string(arr[ok].astype("int64").astype("datetime64[s]"), unit="s")
    out[ok] = np.char.replace(s, "T", " ")
    return out


def to_date_str(ts) -> np.ndarray:
    arr = np.asarray(ts, dtype="float64")
    return np.datetime_as_string(arr.astype("int64").astype("datetime64[s]"), unit="D")


def local_hour_to_utc(day_start_utc, local_hour, utc_offset_hours):
    """Timestamp for `local_hour` (fractional) on the local calendar day starting at `day_start_utc`."""
    return day_start_utc + (np.asarray(local_hour) - np.asarray(utc_offset_hours)) * HOUR


def daily_index(start: date, end: date) -> pd.DatetimeIndex:
    return pd.date_range(start, end, freq="D")
