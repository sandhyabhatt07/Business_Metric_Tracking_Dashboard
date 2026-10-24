"""Point-in-time features for the churn model.

A snapshot at date `t` describes each account that was paying on `t`, using only data from before `t`.
The label says whether the account churned in the 60 days from `t` on. Building every feature from
the past only is what keeps the model honest: nothing it learns from could be unknown at `t`.
"""

import numpy as np
import pandas as pd

from .warehouse import query

WINDOW = 28
HORIZON_DAYS = 60
PLAN_TIER = {"Starter": 1, "Growth": 2, "Business": 3, "Enterprise": 4}


def load_inputs() -> dict[str, pd.DataFrame]:
    return {
        "activity": query("select account_id, user_id, activity_date, events, sessions, reports_created "
                          "from core.fct_user_daily_activity"),
        "users": query("select account_id, created_at from core.dim_user where not is_internal"),
        "subs": query("select account_id, plan, billing_interval, seats, discount_pct, currency, mrr_local, "
                      "started_at, ended_at, status from staging.stg_app__subscriptions"),
        "accounts": query("select account_id, segment, signup_channel, first_paid_at from core.dim_account "
                          "where not is_internal"),
        "fx": query("select rate_date, currency, usd_rate from intermediate.int_fx_rates_daily"),
    }


def snapshot(inputs: dict[str, pd.DataFrame], t: pd.Timestamp) -> pd.DataFrame:
    """One row per account paying at `t`, with features and (when known) the 60-day churn label."""
    subs = inputs["subs"].copy()
    for col in ("started_at", "ended_at"):
        subs[col] = pd.to_datetime(subs[col])

    live = subs[(subs["started_at"] <= t) & (subs["ended_at"].isna() | (subs["ended_at"] > t))]
    live = live.sort_values("started_at").groupby("account_id").last()
    if live.empty:
        return pd.DataFrame()

    first_start = subs.groupby("account_id")["started_at"].min()
    canceled = subs[subs["status"] == "canceled"].set_index("account_id")["ended_at"]
    horizon = t + pd.Timedelta(days=HORIZON_DAYS)

    fx = inputs["fx"].assign(rate_date=lambda d: pd.to_datetime(d["rate_date"]))
    rate = fx[fx["rate_date"] == t.normalize()].set_index("currency")["usd_rate"]

    df = pd.DataFrame(index=live.index)
    df["mrr_usd"] = live["mrr_local"] / live["currency"].map(rate)
    df["seats"] = live["seats"]
    df["plan_tier"] = live["plan"].map(PLAN_TIER)
    df["is_annual"] = (live["billing_interval"] == "year").astype(int)
    df["discount_pct"] = live["discount_pct"]
    tenure_days = (t - first_start.reindex(df.index)).dt.days
    df["tenure_months"] = tenure_days / 30.44
    # Annual plans can only churn at renewal: how far away is the next one?
    months_into_term = np.floor(df["tenure_months"]) % 12
    df["months_to_renewal"] = np.where(df["is_annual"] == 1, 12 - months_into_term, 1)

    users = inputs["users"].assign(created_at=lambda d: pd.to_datetime(d["created_at"]))
    df["users_total"] = users[users["created_at"] < t].groupby("account_id").size().reindex(df.index).fillna(0)
    df["users_added_56d"] = (users[(users["created_at"] < t) & (users["created_at"] >= t - pd.Timedelta(days=56))]
                             .groupby("account_id").size().reindex(df.index).fillna(0))

    act = inputs["activity"].assign(activity_date=lambda d: pd.to_datetime(d["activity_date"]))
    act = act[act["account_id"].isin(df.index) & (act["activity_date"] < t)]
    recent = act[act["activity_date"] >= t - pd.Timedelta(days=WINDOW)]
    prior = act[(act["activity_date"] < t - pd.Timedelta(days=WINDOW))
                & (act["activity_date"] >= t - pd.Timedelta(days=2 * WINDOW))]

    g = recent.groupby("account_id")
    df["active_users_28d"] = g["user_id"].nunique().reindex(df.index).fillna(0)
    df["user_days_28d"] = g.size().reindex(df.index).fillna(0)
    df["sessions_28d"] = g["sessions"].sum().reindex(df.index).fillna(0)
    df["reports_28d"] = g["reports_created"].sum().reindex(df.index).fillna(0)
    prior_days = prior.groupby("account_id").size().reindex(df.index).fillna(0)
    df["user_days_trend"] = (df["user_days_28d"] + 1) / (prior_days + 1)
    df["active_share_of_seats"] = df["active_users_28d"] / df["seats"]
    last_seen = act.groupby("account_id")["activity_date"].max().reindex(df.index)
    df["days_since_last_active"] = (t - last_seen).dt.days.fillna(365)

    acc = inputs["accounts"].set_index("account_id")
    df = df.join(acc[["segment", "signup_channel"]])

    df["churned_60d"] = canceled.reindex(df.index).between(t, horizon, inclusive="left").astype(int)
    df["snapshot_date"] = t
    return df.reset_index()


def snapshots(inputs: dict[str, pd.DataFrame], dates) -> pd.DataFrame:
    return pd.concat([snapshot(inputs, pd.Timestamp(d)) for d in dates], ignore_index=True)
