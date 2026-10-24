"""Users: one owner per account, teammates invited after activation, and internal QA users."""

import numpy as np
import pandas as pd

from . import reference as ref
from .config import Config
from .timeline import DAY, epoch

MEMBERS_MEAN = {"SMB": 1.5, "Mid-Market": 5.0, "Enterprise": 15.0}
INVITE_GAP_DAYS = {"SMB": 25.0, "Mid-Market": 12.0, "Enterprise": 6.0}
INTERNAL_ACCOUNT_ID = 1000


def _email_domain(names: pd.Series) -> pd.Series:
    words = names.str.lower().str.split(" ")
    return words.str[0] + words.str[1] + ".example"


def generate_users(cfg: Config, rng: np.random.Generator, accounts: pd.DataFrame,
                   funnel: pd.DataFrame, lifecycle: pd.DataFrame) -> pd.DataFrame:
    end_ts = epoch(cfg.end_date) + DAY
    acc = accounts.merge(funnel, on="account_id").merge(lifecycle, on="account_id")
    domain = _email_domain(acc["workspace_name"])

    owners = pd.DataFrame({
        "account_id": acc["account_id"],
        "role": "owner",
        "signup_ts": acc["created_ts"],
        "signup_channel": acc["signup_channel"],
        "onboarding_flow": acc["onboarding_flow"],
        "domain": domain,
        "activity_factor": rng.uniform(0.95, 1.25, len(acc)),
    })

    member_rows = []
    paid = acc["paid_ts"].notna().to_numpy()
    for i, row in enumerate(acc.itertuples(index=False)):
        if np.isnan(row.activated_ts):
            continue
        k = rng.poisson(MEMBERS_MEAN[row.segment] * (1.0 if paid[i] else 0.4))
        if k == 0:
            continue
        joins = row.activated_ts + np.cumsum(rng.exponential(INVITE_GAP_DAYS[row.segment] * DAY, k))
        joins = joins[joins < min(row.active_until_ts, end_ts)]
        for ts in joins:
            member_rows.append((row.account_id, ts, domain.iat[i]))
    members = pd.DataFrame(member_rows, columns=["account_id", "signup_ts", "domain"])
    members["role"] = "member"
    members["signup_channel"] = "invite"
    members["onboarding_flow"] = None
    members["activity_factor"] = rng.uniform(0.45, 1.1, len(members))

    internal = pd.DataFrame({
        "account_id": INTERNAL_ACCOUNT_ID,
        "role": np.where(np.arange(cfg.n_internal_users) == 0, "owner", "member"),
        "signup_ts": epoch(cfg.start_date) + rng.uniform(0, 30 * DAY, cfg.n_internal_users),
        "signup_channel": "internal",
        "onboarding_flow": "classic",
        "domain": ref.INTERNAL_EMAIL_DOMAIN,
        "activity_factor": 1.0,
    })

    users = pd.concat([internal, owners, members], ignore_index=True).sort_values("signup_ts", kind="stable")
    users = users.reset_index(drop=True)
    users["user_id"] = np.arange(50_001, 50_001 + len(users))
    users["email"] = np.where(users["domain"] == ref.INTERNAL_EMAIL_DOMAIN,
                              "qa" + users["user_id"].astype(str), "user" + users["user_id"].astype(str))
    users["email"] = users["email"] + "@" + users["domain"]
    users["primary_platform"] = rng.choice(["web", "ios", "android"], len(users), p=[0.70, 0.18, 0.12])
    return users.drop(columns="domain")
