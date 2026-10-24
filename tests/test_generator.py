import json
import sqlite3
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from data_generator.config import Config
from data_generator.generate import build, write_all
from data_generator.timeline import DAY, epoch

CFG = replace(Config(), n_accounts=400, n_internal_users=5)


@pytest.fixture(scope="module")
def sources():
    return build(CFG)


def test_same_seed_same_data():
    a, b = build(CFG), build(CFG)
    pd.testing.assert_frame_equal(a["events"], b["events"])
    pd.testing.assert_frame_equal(a["invoices"], b["invoices"])


def test_referential_integrity(sources):
    accounts = set(sources["accounts"]["account_id"]) | {1000}
    assert set(sources["users"]["account_id"]) <= accounts
    assert set(sources["subscriptions"]["account_id"]) <= accounts
    assert set(sources["invoices"]["subscription_id"]) <= set(sources["subscriptions"]["subscription_id"])
    user_ids = set(sources["users"]["user_id"])
    assert set(sources["events"]["user_id"].dropna()) <= user_ids


def test_funnel_milestones_are_ordered(sources):
    f = sources["funnel"]
    for earlier, later in [("onboarded_ts", "activated_ts"), ("activated_ts", "trial_ts"), ("trial_ts", "paid_ts")]:
        both = f[[earlier, later]].dropna()
        assert (both[earlier] <= both[later]).all()
    # Every paying account appears in billing.
    assert set(f.loc[f["paid_ts"].notna(), "account_id"]) == set(sources["subscriptions"]["account_id"])


def test_subscriptions_do_not_overlap(sources):
    s = sources["subscriptions"].sort_values(["account_id", "started_ts"])
    ended = s["ended_ts"].fillna(np.inf)
    assert (ended >= s["started_ts"]).all()
    nxt = s.groupby("account_id")["started_ts"].shift(-1)
    assert (ended[nxt.notna()] <= nxt[nxt.notna()]).all()
    assert (s.groupby("account_id")["ended_ts"].apply(lambda v: v.isna().sum()) <= 1).all()


def test_experiment_only_assigns_signups_in_window(sources):
    a = sources["assignments"]
    assert a["variant"].isin(["control", "treatment"]).all()
    assert (a["assigned_ts"] >= epoch(CFG.experiment_start)).all()
    assert (a["assigned_ts"] <= epoch(CFG.experiment_end) + DAY + 1).all()


def test_planted_data_quality_issues(sources):
    ev = sources["events"]
    assert ev["event_id"].duplicated().any(), "retried uploads should duplicate event ids"
    assert ev["user_id"].isna().any(), "anonymous events should exist"
    assert (ev["event_ts"] > ev["received_ts"] + DAY).any(), "clock-skewed events should exist"
    crm_ids = [r["properties"]["app_account_id"] for r in sources["crm"]]
    assert len(crm_ids) > len(set(crm_ids)), "CRM should contain duplicate companies"


def test_written_sources(sources, tmp_path):
    counts = write_all(CFG, tmp_path, sources)
    with sqlite3.connect(tmp_path / "app_db" / "app.sqlite") as con:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        n_events = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert tables == {"accounts", "users", "events", "subscriptions", "invoices", "experiment_assignments"}
    assert n_events == counts["app_db.events"] == len(sources["events"])

    page = json.loads((tmp_path / "crm" / "companies_page_0001.json").read_text())
    assert {"id", "properties"} <= set(page["results"][0])

    spend = pd.read_csv(sorted((tmp_path / "marketing").glob("*.csv"))[1])
    assert list(spend.columns) == ["Date", "Platform", "Campaign", "Impressions", "Clicks", "Spend", "Currency"]

    fx = json.loads(sorted((tmp_path / "fx").glob("*.json"))[0].read_text())
    assert fx["base"] == "USD" and fx["rates"]
