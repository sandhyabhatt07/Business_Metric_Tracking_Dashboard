"""Generate every raw source for the fictional SaaS company PulseBoard.

    python -m data_generator.generate --out data/raw
    python -m data_generator.generate --out data/raw --accounts 500   # quick small run
"""

import argparse
import time
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from .accounts import generate_accounts
from .billing import generate_billing
from .config import Config
from .events import generate_events
from .external import generate_crm, generate_fx_rates, generate_marketing_spend
from .funnel import generate_funnel
from .lifecycle import generate_lifecycle
from .timeline import epoch
from .users import INTERNAL_ACCOUNT_ID, generate_users
from . import writers


def build(cfg: Config) -> dict:
    """Simulate the business and return every source as in-memory objects."""
    rng = np.random.default_rng(cfg.seed)
    accounts = generate_accounts(cfg, rng)
    funnel, assignments = generate_funnel(cfg, rng, accounts)
    lifecycle = generate_lifecycle(cfg, rng, accounts, funnel)
    users = generate_users(cfg, rng, accounts, funnel, lifecycle)
    subscriptions, invoices = generate_billing(cfg, rng, accounts, lifecycle, users)
    events = generate_events(cfg, rng, accounts, funnel, lifecycle, users)
    return {
        "accounts": accounts, "funnel": funnel, "assignments": assignments, "lifecycle": lifecycle,
        "users": users, "subscriptions": subscriptions, "invoices": invoices, "events": events,
        "crm": generate_crm(cfg, rng, accounts, lifecycle, funnel),
        "marketing": generate_marketing_spend(cfg, rng, accounts),
        "fx": generate_fx_rates(cfg, rng),
    }


def app_db_tables(cfg: Config, s: dict) -> dict[str, pd.DataFrame]:
    users = s["users"]
    owners = users[users["role"] == "owner"].set_index("account_id")["user_id"]
    internal = pd.DataFrame([{"account_id": INTERNAL_ACCOUNT_ID, "workspace_name": "PulseBoard QA",
                              "country": "US", "signup_channel": "internal",
                              "created_ts": epoch(cfg.start_date)}])
    accounts = pd.concat([internal, s["accounts"]], ignore_index=True)
    accounts = accounts[["account_id", "workspace_name", "country", "signup_channel", "created_ts"]]
    accounts.insert(2, "owner_user_id", accounts["account_id"].map(owners))

    assignments = s["assignments"].assign(user_id=s["assignments"]["account_id"].map(owners))
    events = s["events"]

    iso = writers.iso_columns
    return {
        "accounts": iso(accounts, {"created_ts": "created_at"}),
        "users": iso(users[["user_id", "account_id", "email", "role", "signup_channel", "onboarding_flow",
                            "primary_platform", "signup_ts"]], {"signup_ts": "created_at"}),
        "events": iso(events, {"event_ts": "event_ts", "received_ts": "received_at"}),
        "subscriptions": iso(s["subscriptions"],
                             {"started_ts": "started_at", "ended_ts": "ended_at"}),
        "invoices": iso(s["invoices"], {"period_start_ts": "period_start", "period_end_ts": "period_end",
                                        "issued_ts": "issued_at"}),
        "experiment_assignments": iso(assignments[["user_id", "experiment_name", "variant", "assigned_ts"]],
                                      {"assigned_ts": "assigned_at"}),
    }


def write_all(cfg: Config, out: Path, s: dict) -> dict:
    tables = app_db_tables(cfg, s)
    writers.write_app_db(out / "app_db" / "app.sqlite", tables)
    counts = {f"app_db.{k}": len(v) for k, v in tables.items()}
    counts["crm.company_records"] = len(s["crm"])
    counts["crm.pages"] = writers.write_crm(out / "crm", s["crm"])
    counts["marketing.files"] = writers.write_marketing(out / "marketing", s["marketing"])
    counts["fx.files"] = writers.write_fx(out / "fx", s["fx"])
    writers.write_manifest(out / "manifest.json", {"config": asdict(cfg), "row_counts": counts})
    return counts


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=Path("data/raw"))
    p.add_argument("--accounts", type=int, help="number of customer accounts (default 10,000)")
    p.add_argument("--seed", type=int)
    args = p.parse_args()

    cfg = Config()
    if args.accounts:
        cfg = replace(cfg, n_accounts=args.accounts)
    if args.seed is not None:
        cfg = replace(cfg, seed=args.seed)

    t0 = time.time()
    sources = build(cfg)
    counts = write_all(cfg, args.out, sources)
    width = max(map(len, counts))
    for k, v in counts.items():
        print(f"{k:<{width}}  {v:>10,}")
    print(f"done in {time.time() - t0:.0f}s -> {args.out}")


if __name__ == "__main__":
    main()
