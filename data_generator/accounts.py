"""Accounts (customer workspaces): when they signed up, who they are, how engaged they will be."""

import numpy as np
import pandas as pd

from . import reference as ref
from .config import Config
from .timeline import DAY, daily_index, epoch, local_hour_to_utc


def signup_day_weights(cfg: Config) -> np.ndarray:
    days = daily_index(cfg.start_date, cfg.end_date)
    trend = 1 + 1.8 * np.linspace(0, 1, len(days))
    weekday = np.where(days.dayofweek < 5, 1.15, 0.55)
    season = days.month.map(ref.MONTH_SEASONALITY).to_numpy()
    w = trend * weekday * season
    return w / w.sum()


def _company_names(rng: np.random.Generator, n: int) -> np.ndarray:
    pre = rng.choice(ref.NAME_PREFIXES, n)
    core = rng.choice(ref.NAME_CORES, n)
    suf = rng.choice(ref.NAME_SUFFIXES, n)
    return np.char.add(np.char.add(np.char.add(np.char.add(pre, " "), core), " "), suf)


def generate_accounts(cfg: Config, rng: np.random.Generator) -> pd.DataFrame:
    n = cfg.n_accounts
    day_idx = np.sort(rng.choice(cfg.n_days, size=n, p=signup_day_weights(cfg)))

    segment = rng.choice(ref.SEGMENTS, n, p=ref.SEGMENT_MIX)
    lo = np.array([ref.EMPLOYEE_RANGES[s][0] for s in segment])
    hi = np.array([ref.EMPLOYEE_RANGES[s][1] for s in segment])
    # Log-uniform headcount inside the segment band.
    employees = np.exp(rng.uniform(np.log(lo), np.log(hi + 1))).astype(int)

    region = rng.choice(list(ref.REGION_MIX), n, p=list(ref.REGION_MIX.values()))
    country = np.empty(n, dtype=object)
    for r in ref.REGION_MIX:
        codes = [c for c, v in ref.COUNTRIES.items() if v[0] == r]
        weights = np.array([ref.COUNTRIES[c][1] for c in codes])
        mask = region == r
        country[mask] = rng.choice(codes, mask.sum(), p=weights / weights.sum())
    currency = np.array([ref.COUNTRIES[c][2] for c in country])
    utc_offset = np.array([ref.COUNTRIES[c][3] for c in country])

    channel = np.empty(n, dtype=object)
    for s in ref.SEGMENTS:
        mask = segment == s
        channel[mask] = rng.choice(ref.CHANNELS, mask.sum(), p=ref.CHANNEL_MIX[s])

    local_hour = np.clip(rng.normal(12.5, 3.0, n), 6, 23.5)
    created_ts = local_hour_to_utc(epoch(cfg.start_date) + day_idx * DAY, local_hour, utc_offset)
    created_ts = np.clip(created_ts, epoch(cfg.start_date), epoch(cfg.end_date) + DAY - 3600)

    # Latent engagement drives product usage, conversion and churn. Never exported.
    engagement = np.clip(rng.beta(2.5, 2.5, n) + np.select(
        [segment == "Enterprise", segment == "Mid-Market"], [0.06, 0.03], 0.0), 0.01, 0.99)

    return pd.DataFrame({
        "account_id": np.arange(1001, 1001 + n),
        "workspace_name": _company_names(rng, n),
        "created_ts": created_ts,
        "segment": segment,
        "employee_count": employees,
        "industry": rng.choice(ref.INDUSTRIES, n),
        "region": region,
        "country": country,
        "currency": currency,
        "utc_offset": utc_offset,
        "signup_channel": channel,
        "engagement": engagement,
    })
