"""Product event stream: sessions and in-app actions for every user, plus funnel milestone events."""

import numpy as np
import pandas as pd

from .config import Config
from .timeline import DAY, HOUR, epoch
from .users import INTERNAL_ACCOUNT_ID

ACTIONS = np.array(["view_dashboard", "run_query", "create_report", "share_report", "export_data"])
ACTION_P = [0.50, 0.20, 0.12, 0.08, 0.10]
PLATFORMS = np.array(["web", "ios", "android"])


def _day_factors(cfg: Config) -> np.ndarray:
    days = pd.date_range(cfg.start_date, cfg.end_date, freq="D")
    f = np.where(days.dayofweek < 5, 1.0, 0.25)
    f = f * np.select([(days.month == 12) & (days.day >= 18), days.month == 12, days.month == 8],
                      [0.55, 0.85, 0.90], 1.0)
    f[(days == pd.Timestamp(cfg.outage_date))] *= 0.45
    return f


def generate_events(cfg: Config, rng: np.random.Generator, accounts: pd.DataFrame, funnel: pd.DataFrame,
                    lifecycle: pd.DataFrame, users: pd.DataFrame) -> pd.DataFrame:
    start_ts, end_ts = epoch(cfg.start_date), epoch(cfg.end_date) + DAY
    day_factor = _day_factors(cfg)
    acc = accounts.merge(funnel, on="account_id").merge(lifecycle, on="account_id").set_index("account_id")
    u = users.merge(acc[["engagement", "utc_offset", "paid_ts", "churn_ts", "activated_ts",
                         "active_until_ts"]], left_on="account_id", right_index=True, how="left")
    internal = (u["account_id"] == INTERNAL_ACCOUNT_ID).to_numpy()
    u.loc[internal, ["engagement", "utc_offset"]] = [0.9, -5.0]

    s_user, s_ts, s_lam, s_report, s_platform = [], [], [], [], []
    for i, row in enumerate(u.itertuples(index=False)):
        first_day = int((row.signup_ts - start_ts) // DAY)
        stop = row.active_until_ts
        if not np.isnan(row.churn_ts):
            stop = row.churn_ts + rng.uniform(0, 10) * DAY
        last_day = int((min(stop, end_ts - 1) - start_ts) // DAY) if not internal[i] else cfg.n_days - 1
        if last_day < first_day:
            last_day = first_day
        days = np.arange(first_day, last_day + 1)
        age = days - first_day

        if internal[i]:
            p = 0.75 * np.where(day_factor[days] < 0.5, 0.07, 1.0)
        else:
            p_paid = (0.12 + 0.6 * row.engagement) * row.activity_factor
            paid_day = np.inf if np.isnan(row.paid_ts) else (row.paid_ts - start_ts) // DAY
            is_paid = days >= paid_day
            p = np.where(is_paid, p_paid * np.exp(-age / 600),
                         0.55 * p_paid * np.exp(-age / (40 if np.isinf(paid_day) else 90)))
            p = p * day_factor[days]
            if not np.isnan(row.churn_ts):
                to_churn = ((row.churn_ts - start_ts) / DAY) - days
                p = p * np.where(to_churn < 60, 0.35 + 0.65 * np.clip(to_churn, 0, 60) / 60, 1.0)
        active = rng.random(len(days)) < np.clip(p, 0, 0.97)
        active[0] = True
        active_days = days[active]

        n_sess = 1 + rng.poisson(0.35, len(active_days))
        sess_day = np.repeat(active_days, n_sess)
        local_hour = np.clip(rng.normal(13, 2.8, len(sess_day)), 6, 23.9)
        ts = start_ts + sess_day * DAY + (local_hour - row.utc_offset) * HOUR
        # The signup-day session starts at signup.
        ts[sess_day == first_day] = np.maximum(ts[sess_day == first_day], row.signup_ts + 5)
        ts = ts[ts < end_ts]

        lam = 1.2 if np.isnan(row.paid_ts) else 1.8
        can_report = np.ones(len(ts), bool) if internal[i] else (
            ~np.isnan(row.activated_ts) & (ts > np.nan_to_num(row.activated_ts, nan=np.inf)))
        platform = np.where(rng.random(len(ts)) < 0.8, row.primary_platform,
                            rng.choice(PLATFORMS, len(ts)))
        s_user.append(np.full(len(ts), row.user_id))
        s_ts.append(ts)
        s_lam.append(np.full(len(ts), lam * (2.0 if internal[i] else 1.0)))
        s_report.append(can_report)
        s_platform.append(platform)

    s_user, s_ts = np.concatenate(s_user), np.concatenate(s_ts)
    s_lam, s_report, s_platform = np.concatenate(s_lam), np.concatenate(s_report), np.concatenate(s_platform)
    session_id = np.arange(1, len(s_ts) + 1)

    # In-session actions follow the session_start a few minutes apart.
    n_act = rng.poisson(s_lam)
    act_sess = np.repeat(np.arange(len(s_ts)), n_act)
    gaps = rng.exponential(240, len(act_sess))
    cum = np.cumsum(gaps)
    first = np.cumsum(n_act) - n_act
    has = n_act > 0
    offset = cum - np.repeat((cum - gaps)[first[has]], n_act[has])
    act_name = rng.choice(ACTIONS, len(act_sess), p=ACTION_P)
    act_name = np.where((act_name == "create_report") & ~s_report[act_sess], "view_dashboard", act_name)

    frames = [
        pd.DataFrame({"user_id": s_user, "session_id": session_id, "event_name": "session_start",
                      "event_ts": s_ts, "platform": s_platform}),
        pd.DataFrame({"user_id": s_user[act_sess], "session_id": session_id[act_sess],
                      "event_name": act_name, "event_ts": s_ts[act_sess] + offset,
                      "platform": s_platform[act_sess]}),
    ]
    frames.append(_milestone_events(u, funnel, users))
    ev = pd.concat(frames, ignore_index=True)
    ev = ev[(ev["event_ts"] >= start_ts) & (ev["event_ts"] < end_ts)]
    return _add_noise(cfg, rng, ev)


def _milestone_events(u: pd.DataFrame, funnel: pd.DataFrame, users: pd.DataFrame) -> pd.DataFrame:
    owners = u[u["role"] == "owner"][["user_id", "account_id", "signup_ts", "primary_platform"]]
    owners = owners.merge(funnel, on="account_id", how="left")
    rows = [owners.assign(event_name="signup", event_ts=owners["signup_ts"])]
    for col, name in [("onboarded_ts", "onboarding_completed"), ("activated_ts", "report_created"),
                      ("trial_ts", "trial_started")]:
        hit = owners[owners[col].notna()]
        rows.append(hit.assign(event_name=name, event_ts=hit[col]))

    members = u[u["role"] == "member"][["user_id", "account_id", "signup_ts", "primary_platform"]]
    rows.append(members.assign(event_name="invite_accepted", event_ts=members["signup_ts"]))
    inviter = owners.set_index("account_id")[["user_id", "signup_ts"]]
    sent = members.join(inviter, on="account_id", rsuffix="_owner").dropna(subset=["user_id_owner"])
    sent_ts = np.maximum(sent["signup_ts"] - 3600 * 6, sent["signup_ts_owner"] + 60)
    rows.append(pd.DataFrame({"user_id": sent["user_id_owner"].astype(int), "event_name": "invite_sent",
                              "event_ts": sent_ts, "primary_platform": sent["primary_platform"]}))

    ev = pd.concat(rows, ignore_index=True)
    # Milestones happen inside a session we don't track; give them their own session ids later.
    return pd.DataFrame({"user_id": ev["user_id"], "session_id": np.nan, "event_name": ev["event_name"],
                         "event_ts": ev["event_ts"], "platform": ev["primary_platform"]})


def _add_noise(cfg: Config, rng: np.random.Generator, ev: pd.DataFrame) -> pd.DataFrame:
    """Plant the data quality problems documented in docs/data_sources.md."""
    start_ts = epoch(cfg.start_date)
    ev = ev.sort_values("event_ts", kind="stable", ignore_index=True)
    n = len(ev)

    # Milestone events without a session get a fresh one.
    missing = ev["session_id"].isna().to_numpy()
    sess = ev["session_id"].to_numpy(dtype="float64", copy=True)
    sess[missing] = np.nanmax(sess) + 1 + np.arange(missing.sum())
    ev["session_id"] = sess.astype("int64")

    mobile = ev["platform"].isin(["ios", "android"]).to_numpy()
    day = ((ev["event_ts"].to_numpy() - start_ts) // DAY).astype(int)
    ev["app_version"] = np.where(mobile, "3." + (day // 56).astype(str) + "." + (day % 3).astype(str), None)

    # Mobile clients batch events offline: 3% arrive 1-72 hours late.
    lag = rng.exponential(4, n)
    late = mobile & (rng.random(n) < 0.03)
    lag[late] += rng.uniform(1, 72, late.sum()) * HOUR
    ev["received_ts"] = ev["event_ts"] + lag

    # iOS bug: session_start fires twice (new event id) for three days.
    bug_lo, bug_hi = epoch(cfg.ios_double_fire_start), epoch(cfg.ios_double_fire_end) + DAY
    doubled = ev[(ev["platform"] == "ios") & (ev["event_name"] == "session_start")
                 & ev["event_ts"].between(bug_lo, bug_hi)].copy()
    doubled["event_ts"] += 0.4
    doubled["received_ts"] += 0.4
    ev = pd.concat([ev, doubled]).sort_values("event_ts", kind="stable", ignore_index=True)
    ev.insert(0, "event_id", np.arange(1, len(ev) + 1))

    # Device clocks set wrong: 0.02% of events claim to be from a year later.
    skew = rng.random(len(ev)) < 0.0002
    ev.loc[skew, "event_ts"] += 365 * DAY
    # Anonymous / bot traffic with no user.
    anon = rng.random(len(ev)) < 0.001
    ev["user_id"] = ev["user_id"].astype("Int64")
    ev.loc[anon, "user_id"] = pd.NA
    # Retried uploads: 0.3% of rows delivered twice with the same event_id.
    dupes = ev[rng.random(len(ev)) < 0.003].copy()
    dupes["received_ts"] += rng.uniform(1, 600, len(dupes))
    return pd.concat([ev, dupes]).sort_values(["received_ts"], ignore_index=True)
