"""Signup funnel per account: onboarding, activation, trial, paid conversion, plus the onboarding A/B test.

Milestones that would land after the end of the simulated window have not happened yet and are NaN.
"""

import numpy as np
import pandas as pd

from .config import Config
from .timeline import DAY, epoch

ACTIVATION_BASE = {"SMB": 0.55, "Mid-Market": 0.60, "Enterprise": 0.66}
CONVERSION_BASE = {"SMB": 0.38, "Mid-Market": 0.46, "Enterprise": 0.55}
TRIAL_DAYS = 14


def generate_funnel(cfg: Config, rng: np.random.Generator, accounts: pd.DataFrame):
    n = len(accounts)
    signup = accounts["created_ts"].to_numpy()
    seg = accounts["segment"].to_numpy()
    e = accounts["engagement"].to_numpy()
    end_ts = epoch(cfg.end_date) + DAY

    # Onboarding flow: classic before the test, 50/50 during it, guided after rollout.
    in_test = (signup >= epoch(cfg.experiment_start)) & (signup < epoch(cfg.experiment_end) + DAY)
    variant = np.where(rng.random(n) < 0.5, "treatment", "control")
    flow = np.where(signup >= epoch(cfg.rollout_date), "guided_checklist", "classic")
    flow = np.where(in_test & (variant == "treatment"), "guided_checklist", flow)
    guided = flow == "guided_checklist"

    onboarded = rng.random(n) < 0.74
    onboard_ts = signup + rng.exponential(25 * 60, n)

    p_act = np.vectorize(ACTIVATION_BASE.get)(seg) + 0.30 * (e - 0.5) + np.where(guided, cfg.activation_lift, 0)
    activated = onboarded & (rng.random(n) < np.clip(p_act, 0.02, 0.98))
    activated_ts = onboard_ts + rng.gamma(1.2, 1.4 * DAY, n)

    p_trial = np.where(activated, np.clip(0.55 * (0.7 + 0.6 * e), 0, 0.95), np.where(onboarded, 0.08, 0.02))
    trialed = rng.random(n) < p_trial
    trial_ts = np.where(activated, activated_ts, onboard_ts) + rng.exponential(4 * DAY, n)

    p_conv = np.vectorize(CONVERSION_BASE.get)(seg) * (0.6 + 0.8 * e) * np.where(activated, 1.0, 0.3)
    converted = trialed & (rng.random(n) < np.clip(p_conv, 0, 0.95))
    paid_ts = trial_ts + np.maximum(TRIAL_DAYS * DAY + rng.normal(0, DAY, n), DAY)

    def censor(happened, ts):
        return np.where(happened & (ts < end_ts), ts, np.nan)

    funnel = pd.DataFrame({
        "account_id": accounts["account_id"].to_numpy(),
        "onboarding_flow": flow,
        "onboarded_ts": censor(onboarded, onboard_ts),
        "activated_ts": censor(activated, activated_ts),
        "trial_ts": censor(trialed, trial_ts),
        "paid_ts": censor(converted, paid_ts),
    })
    # A later milestone can't exist if an earlier one was censored.
    funnel.loc[funnel["onboarded_ts"].isna(), ["activated_ts", "trial_ts", "paid_ts"]] = np.nan
    funnel.loc[funnel["trial_ts"].isna(), "paid_ts"] = np.nan

    assignments = pd.DataFrame({
        "account_id": accounts["account_id"].to_numpy()[in_test],
        "experiment_name": cfg.experiment_name,
        "variant": variant[in_test],
        "assigned_ts": signup[in_test] + 1.0,
    })
    return funnel, assignments
