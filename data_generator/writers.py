"""Write each source in the format its real-world system would hand us."""

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from .timeline import to_iso

APP_DB_DDL = """
CREATE TABLE accounts (
    account_id      INTEGER PRIMARY KEY,
    workspace_name  TEXT NOT NULL,
    owner_user_id   INTEGER,
    country         TEXT,
    signup_channel  TEXT,
    created_at      TEXT NOT NULL
);
CREATE TABLE users (
    user_id          INTEGER PRIMARY KEY,
    account_id       INTEGER NOT NULL REFERENCES accounts(account_id),
    email            TEXT NOT NULL,
    role             TEXT NOT NULL,
    signup_channel   TEXT,
    onboarding_flow  TEXT,
    primary_platform TEXT,
    created_at       TEXT NOT NULL
);
CREATE TABLE events (
    event_id     INTEGER,
    user_id      INTEGER,
    session_id   INTEGER,
    event_name   TEXT NOT NULL,
    event_ts     TEXT NOT NULL,
    received_at  TEXT NOT NULL,
    platform     TEXT,
    app_version  TEXT
);
CREATE TABLE subscriptions (
    subscription_id  INTEGER PRIMARY KEY,
    account_id       INTEGER NOT NULL REFERENCES accounts(account_id),
    plan             TEXT NOT NULL,
    billing_interval TEXT NOT NULL,
    seats            INTEGER NOT NULL,
    unit_price_minor INTEGER NOT NULL,
    discount_pct     REAL NOT NULL,
    currency         TEXT NOT NULL,
    status           TEXT NOT NULL,
    cancel_reason    TEXT,
    started_at       TEXT NOT NULL,
    ended_at         TEXT
);
CREATE TABLE invoices (
    invoice_id      INTEGER PRIMARY KEY,
    account_id      INTEGER NOT NULL REFERENCES accounts(account_id),
    subscription_id INTEGER NOT NULL REFERENCES subscriptions(subscription_id),
    status          TEXT NOT NULL,
    amount_minor    INTEGER NOT NULL,
    currency        TEXT NOT NULL,
    period_start    TEXT NOT NULL,
    period_end      TEXT NOT NULL,
    issued_at       TEXT NOT NULL
);
CREATE TABLE experiment_assignments (
    user_id         INTEGER NOT NULL REFERENCES users(user_id),
    experiment_name TEXT NOT NULL,
    variant         TEXT NOT NULL,
    assigned_at     TEXT NOT NULL
);
CREATE INDEX ix_events_received_at ON events(received_at);
"""


def write_app_db(path: Path, tables: dict[str, pd.DataFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    with sqlite3.connect(path) as con:
        con.executescript(APP_DB_DDL)
        for name, df in tables.items():
            df = df.astype(object).where(df.notna(), None)
            cols = ", ".join(df.columns)
            marks = ", ".join("?" * len(df.columns))
            con.executemany(f"INSERT INTO {name} ({cols}) VALUES ({marks})", df.itertuples(index=False))


def iso_columns(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    out = df.copy()
    for src, dst in mapping.items():
        out[dst] = to_iso(out.pop(src))
    return out


def write_crm(dir_: Path, records: list[dict], page_size: int = 500) -> int:
    dir_.mkdir(parents=True, exist_ok=True)
    pages = [records[i:i + page_size] for i in range(0, len(records), page_size)]
    for n, page in enumerate(pages, start=1):
        nxt = {"next": {"after": str(n * page_size)}} if n < len(pages) else {}
        (dir_ / f"companies_page_{n:04d}.json").write_text(
            json.dumps({"results": page, "paging": nxt}, indent=1))
    return len(pages)


def write_marketing(dir_: Path, spend: pd.DataFrame) -> int:
    """One CSV per month, US dates and formatted numbers. Each re-export repeats the previous month's last day."""
    dir_.mkdir(parents=True, exist_ok=True)
    month = spend["date"].dt.to_period("M")
    files = 0
    for period in month.unique():
        lo = period.start_time - pd.Timedelta(days=1)
        chunk = spend[(spend["date"] >= lo) & (spend["date"] <= period.end_time)].copy()
        chunk["date"] = chunk["date"].dt.strftime("%m/%d/%Y")
        chunk["spend"] = chunk["spend"].map(lambda v: f"{v:,.2f}")
        chunk["currency"] = "USD"
        chunk.rename(columns={"date": "Date", "platform": "Platform", "campaign_name": "Campaign",
                              "impressions": "Impressions", "clicks": "Clicks", "spend": "Spend",
                              "currency": "Currency"}).to_csv(
            dir_ / f"ad_spend_{period.year}_{period.month:02d}.csv", index=False)
        files += 1
    return files


def write_fx(dir_: Path, rates: pd.DataFrame) -> int:
    """One JSON per month in the shape of a time-series FX API response."""
    dir_.mkdir(parents=True, exist_ok=True)
    month = rates["date"].dt.to_period("M")
    files = 0
    for period, chunk in rates.groupby(month):
        body = {
            "amount": 1.0, "base": "USD",
            "start_date": chunk["date"].min().strftime("%Y-%m-%d"),
            "end_date": chunk["date"].max().strftime("%Y-%m-%d"),
            "rates": {d.strftime("%Y-%m-%d"): {c: float(r[c]) for c in rates.columns if c != "date"}
                      for d, (_, r) in zip(chunk["date"], chunk.iterrows())},
        }
        (dir_ / f"usd_rates_{period.year}_{period.month:02d}.json").write_text(json.dumps(body, indent=1))
        files += 1
    return files


def write_manifest(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, default=lambda o: o.isoformat() if hasattr(o, "isoformat")
                               else int(o) if isinstance(o, np.integer) else str(o)))
