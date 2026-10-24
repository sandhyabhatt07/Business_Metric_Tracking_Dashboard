"""Subscriptions and invoices for paying accounts. Prices are in the account's local currency."""

import numpy as np
import pandas as pd

from . import reference as ref
from .config import Config
from .timeline import DAY, HOUR, add_months


def _upgrade(plan: str) -> str:
    i = ref.PLAN_ORDER.index(plan)
    return ref.PLAN_ORDER[min(i + 1, len(ref.PLAN_ORDER) - 1)]


def _downgrade(plan: str) -> str:
    return ref.PLAN_ORDER[max(ref.PLAN_ORDER.index(plan) - 1, 0)]


def generate_billing(cfg: Config, rng: np.random.Generator, accounts: pd.DataFrame,
                     lifecycle: pd.DataFrame, users: pd.DataFrame):
    acc = accounts.merge(lifecycle, on="account_id")
    acc = acc[acc["billing_interval"].notna()]
    joins = users.groupby("account_id")["signup_ts"].apply(np.sort).to_dict()

    subs, invoices = [], []
    sub_id = 7_000_001
    for row in acc.itertuples(index=False):
        months = 12 if row.billing_interval == "year" else 1
        plan = rng.choice(ref.PLAN_ORDER, p=ref.PLAN_MIX[row.segment])
        discount = ref.ANNUAL_DISCOUNT if months == 12 else 0.0
        if plan == "Enterprise":
            discount += round(rng.uniform(0.0, 0.25), 2)
        account_joins = joins[row.account_id]
        current = None

        for start in row.period_starts:
            users_now = int(np.searchsorted(account_joins, start, side="right"))
            if current is not None:
                if plan == "Starter" and users_now > 8 and rng.random() < 0.35:
                    plan = "Growth"
                elif rng.random() < 0.012:
                    plan = _upgrade(plan)
                elif rng.random() < 0.006:
                    plan = _downgrade(plan)
            price_usd, min_seats = ref.PLANS[plan]
            seats = max(users_now, min_seats)
            if current is None or current["plan"] != plan or current["seats"] != seats:
                if current is not None:
                    current["ended_ts"], current["status"] = start, "changed"
                    subs.append(current)
                current = {
                    "subscription_id": sub_id, "account_id": row.account_id, "plan": plan,
                    "billing_interval": row.billing_interval, "seats": seats,
                    "unit_price_minor": int(round(price_usd * ref.PRICE_BOOK[row.currency] * 100)),
                    "discount_pct": round(discount * 100, 1), "currency": row.currency,
                    "started_ts": start, "ended_ts": np.nan, "status": "active", "cancel_reason": None,
                }
                sub_id += 1

            amount = round(current["seats"] * current["unit_price_minor"] * months * (1 - discount))
            issued = start + rng.uniform(0, 2 * HOUR)
            base = {"account_id": row.account_id, "subscription_id": current["subscription_id"],
                    "period_start_ts": start, "period_end_ts": add_months(start, months),
                    "amount_minor": amount, "currency": row.currency}
            r = rng.random()
            if r < 0.025:   # card declined, retried a few days later
                invoices.append({**base, "issued_ts": issued, "status": "failed"})
                invoices.append({**base, "issued_ts": issued + rng.uniform(2, 5) * DAY,
                                 "status": "paid"})
            else:
                invoices.append({**base, "issued_ts": issued,
                                 "status": "refunded" if r < 0.03 else "paid"})

        if not np.isnan(row.churn_ts):
            current["ended_ts"], current["status"] = row.churn_ts, "canceled"
            current["cancel_reason"] = row.cancel_reason
        subs.append(current)

    invoices = pd.DataFrame(invoices).sort_values("issued_ts", ignore_index=True)
    invoices["invoice_id"] = np.arange(9_000_001, 9_000_001 + len(invoices))
    return pd.DataFrame(subs), invoices
