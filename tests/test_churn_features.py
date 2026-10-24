import os
from pathlib import Path

import pandas as pd
import pytest

WAREHOUSE = Path(os.getenv("DUCKDB_PATH", Path(__file__).parents[1] / "data" / "warehouse.duckdb"))
pytestmark = pytest.mark.skipif(not WAREHOUSE.exists(), reason="needs a built warehouse (make warehouse dbt)")


def test_snapshot_features_use_only_the_past():
    """Deleting everything after the snapshot date must not change any feature, only the label."""
    from analysis.churn_features import load_inputs, snapshot

    t = pd.Timestamp("2026-03-01")
    inputs = load_inputs()
    full = snapshot(inputs, t)

    past = dict(inputs)
    past["activity"] = inputs["activity"][pd.to_datetime(inputs["activity"]["activity_date"]) < t]
    past["users"] = inputs["users"][pd.to_datetime(inputs["users"]["created_at"]) < t]
    subs = inputs["subs"]
    started = pd.to_datetime(subs["started_at"]) < t
    past["subs"] = subs[started].assign(
        ended_at=subs.loc[started, "ended_at"].where(pd.to_datetime(subs.loc[started, "ended_at"]) < t),
        status=subs.loc[started, "status"].where(pd.to_datetime(subs.loc[started, "ended_at"]) < t, "active"))
    truncated = snapshot(past, t)

    features = [c for c in full.columns if c != "churned_60d"]
    pd.testing.assert_frame_equal(full[features].reset_index(drop=True), truncated[features].reset_index(drop=True))
    assert truncated["churned_60d"].sum() == 0   # no future, no label
