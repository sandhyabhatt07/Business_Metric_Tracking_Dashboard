"""When each account stops being active: churn for paying accounts, abandonment for free ones."""

import numpy as np
import pandas as pd

from . import reference as ref
from .config import Config
from .timeline import DAY, add_months, epoch

MONTHLY_CHURN = {"SMB": 0.040, "Mid-Market": 0.022, "Enterprise": 0.010}


def churn_hazard(segment: str, engagement: float) -> float:
    """Monthly churn probability: less engaged accounts churn much more."""
    return MONTHLY_CHURN[segment] * float(np.exp(1.8 * (0.5 - engagement)))


def generate_lifecycle(cfg: Config, rng: np.random.Generator, accounts: pd.DataFrame,
                       funnel: pd.DataFrame) -> pd.DataFrame:
    end_ts = epoch(cfg.end_date) + DAY
    df = accounts[["account_id", "segment", "engagement", "created_ts"]].merge(funnel, on="account_id")
    n = len(df)

    interval = np.where(rng.random(n) < df["segment"].map(ref.ANNUAL_SHARE), "year", "month")
    renewal_dates, churn_ts = [], np.full(n, np.nan)
    for i, row in enumerate(df.itertuples(index=False)):
        if np.isnan(row.paid_ts):
            renewal_dates.append([])
            continue
        step = 12 if interval[i] == "year" else 1
        h = churn_hazard(row.segment, row.engagement)
        p_leave = h if step == 1 else 1 - (1 - 0.6 * h) ** 12
        starts = [row.paid_ts]
        while True:
            nxt = add_months(row.paid_ts, step * len(starts))
            if nxt >= end_ts:
                break
            if rng.random() < p_leave:
                churn_ts[i] = nxt
                break
            starts.append(nxt)
        renewal_dates.append(starts)

    # Free accounts drift away; how fast depends on how far they got.
    abandon = np.select(
        [df["trial_ts"].notna(), df["activated_ts"].notna()],
        [df["trial_ts"] + 14 * DAY + rng.exponential(20 * DAY, n),
         df["activated_ts"] + rng.exponential(75 * DAY, n)],
        df["created_ts"] + rng.exponential(6 * DAY, n),
    )
    paid = df["paid_ts"].notna().to_numpy()
    active_until = np.where(paid, np.where(np.isnan(churn_ts), np.inf, churn_ts), abandon)

    return pd.DataFrame({
        "account_id": df["account_id"],
        "billing_interval": np.where(paid, interval, None),
        "period_starts": renewal_dates,
        "churn_ts": churn_ts,
        "cancel_reason": np.where(np.isnan(churn_ts), None,
                                  rng.choice(ref.CANCEL_REASONS, n, p=[0.24, 0.2, 0.18, 0.25, 0.05, 0.08])),
        "active_until_ts": active_until,
    })
