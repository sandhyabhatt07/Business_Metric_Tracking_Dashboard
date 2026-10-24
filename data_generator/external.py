"""Non-app sources: the CRM export, the ad-platform spend files and the FX rates feed."""

import numpy as np
import pandas as pd

from . import reference as ref
from .config import Config
from .timeline import DAY, epoch


def generate_crm(cfg: Config, rng: np.random.Generator, accounts: pd.DataFrame,
                 lifecycle: pd.DataFrame, funnel: pd.DataFrame) -> list[dict]:
    """CRM company records, shaped like a HubSpot-style companies API."""
    end_ts = epoch(cfg.end_date) + DAY
    acc = accounts.merge(lifecycle, on="account_id").merge(funnel, on="account_id")
    # 2% of workspaces never synced to the CRM.
    acc = acc[rng.random(len(acc)) >= 0.02].reset_index(drop=True)
    n = len(acc)

    stage = np.select(
        [acc["churn_ts"].notna(), acc["paid_ts"].notna(), acc["trial_ts"].notna()],
        ["former_customer", "customer", "opportunity"], "lead")
    owner = np.where(acc["segment"] == "SMB", ref.SELF_SERVE_OWNER, rng.choice(ref.SALES_REPS, n))
    industry = np.where(rng.random(n) < 0.03, None, acc["industry"])
    created = acc["created_ts"] + rng.uniform(60, 3600, n)
    modified = np.minimum(created + rng.exponential(120 * DAY, n), end_ts - 1)

    def spell(segment):
        return rng.choice(ref.SEGMENT_SPELLINGS[segment])

    records = []
    for i, row in enumerate(acc.itertuples(index=False)):
        props = {
            "name": row.workspace_name,
            "app_account_id": str(row.account_id),
            "segment": spell(row.segment),
            "numberofemployees": int(row.employee_count),
            "industry": industry[i],
            "region": row.region,
            "country": row.country,
            "hubspot_owner": owner[i],
            "lifecyclestage": stage[i],
            "createdate": _iso_z(created[i]),
            "lastmodifieddate": _iso_z(modified[i]),
        }
        records.append({"id": f"{30_000_000 + i}", "properties": props})

        # 1.5% duplicates: a rep re-created the company later, sometimes with an updated segment.
        if rng.random() < 0.015:
            dup = dict(props)
            dup_mod = min(modified[i] + rng.uniform(1, 90) * DAY, end_ts - 1)
            dup["lastmodifieddate"] = _iso_z(dup_mod)
            if row.segment == "SMB" and rng.random() < 0.5:
                dup["segment"] = spell("Mid-Market")
                dup["numberofemployees"] = int(row.employee_count * rng.uniform(1.5, 3)) + 100
            records.append({"id": f"{39_000_000 + i}", "properties": dup})
    return records


def _iso_z(ts: float) -> str:
    return pd.Timestamp(ts, unit="s").strftime("%Y-%m-%dT%H:%M:%S.000Z")


def generate_marketing_spend(cfg: Config, rng: np.random.Generator, accounts: pd.DataFrame) -> pd.DataFrame:
    """Daily ad spend per platform and campaign, as exported by the marketing team."""
    days = pd.date_range(cfg.start_date, cfg.end_date, freq="D")
    signup_day = pd.to_datetime(accounts["created_ts"], unit="s").dt.normalize()
    by_channel = accounts.assign(day=signup_day).groupby(["day", "signup_channel"]).size()

    rows = []
    for platform, (channel, cpa, campaigns) in ref.AD_PLATFORMS.items():
        signups = by_channel.xs(channel, level="signup_channel").reindex(days, fill_value=0).to_numpy()
        share = 1.0 if channel == "paid_search" else (0.6 if platform == "Meta Ads" else 0.4)
        spend = (signups * share * cpa * rng.lognormal(0, 0.25, len(days)) + rng.uniform(20, 60, len(days)))
        weights = rng.dirichlet(np.ones(len(campaigns)) * 3, len(days))
        for j, campaign in enumerate(campaigns):
            s = spend * weights[:, j]
            cpm = rng.uniform(6, 14) if platform != "LinkedIn Ads" else rng.uniform(25, 45)
            impressions = (s / cpm * 1000).astype(int)
            clicks = rng.binomial(impressions, rng.uniform(0.008, 0.03))
            rows.append(pd.DataFrame({"date": days, "platform": platform, "campaign_name": campaign,
                                      "impressions": impressions, "clicks": clicks, "spend": s.round(2)}))
    return pd.concat(rows, ignore_index=True).sort_values(["date", "platform", "campaign_name"],
                                                          ignore_index=True)


def generate_fx_rates(cfg: Config, rng: np.random.Generator) -> pd.DataFrame:
    """USD-based daily rates on business days only, like the ECB reference rates."""
    days = pd.bdate_range(cfg.start_date, cfg.end_date)
    out = {"date": days}
    for cur, start in ref.FX_START.items():
        walk = np.cumsum(rng.normal(0, 0.0035, len(days)))
        out[cur] = np.round(start * np.exp(walk - walk[0]), 4)
    return pd.DataFrame(out)
