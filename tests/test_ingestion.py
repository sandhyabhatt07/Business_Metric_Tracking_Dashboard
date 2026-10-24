import json
from dataclasses import replace
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from data_generator.config import Config
from data_generator.generate import build, write_all
from ingestion import extract
from ingestion.load import LocalLoader, to_ndjson
from ingestion.run import check_raw_tables, load_app_events, load_app_snapshots
from ingestion.schemas import RAW_TABLES
from ingestion.settings import Settings

UTC = timezone.utc


@pytest.fixture(scope="module")
def raw_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("raw")
    cfg = replace(Config(), n_accounts=300, n_internal_users=3)
    write_all(cfg, out, build(cfg))
    return out


@pytest.fixture
def settings(raw_dir, tmp_path):
    return Settings(gcp_project=None, bq_location="US", raw_dataset="raw", bq_sandbox=True,
                    data_dir=raw_dir, landing_dir=tmp_path / "landing", crm_source=str(raw_dir / "crm"),
                    fx_source=str(raw_dir / "fx"), events_lookback_days=3)


def test_extracted_columns_match_raw_schemas(raw_dir):
    db = raw_dir / "app_db" / "app.sqlite"
    samples = {f"app_{t}": extract.extract_app_table(db, t)[:5] for t in extract.APP_TABLES}
    samples["crm_companies"] = extract.extract_crm(str(raw_dir / "crm"))[:5]
    samples["ad_spend"] = extract.extract_ad_spend(raw_dir / "marketing")[:5]
    samples["fx_rates"] = extract.extract_fx(str(raw_dir / "fx"), date(2025, 1, 1), date(2025, 1, 31))[:5]
    for name, rows in samples.items():
        assert rows, name
        to_ndjson(rows, RAW_TABLES[name], "b1")   # raises on any column the schema doesn't know


def test_crm_follows_every_page(raw_dir):
    rows = extract.extract_crm(str(raw_dir / "crm"))
    files = sorted((raw_dir / "crm").glob("*.json"))
    expected = sum(len(json.loads(f.read_text())["results"]) for f in files)
    assert len(rows) == expected
    assert json.loads(rows[0]["_raw"])["id"] == rows[0]["crm_company_id"]


def test_fx_skips_weekends_and_respects_range(raw_dir):
    rows = extract.extract_fx(str(raw_dir / "fx"), date(2025, 3, 3), date(2025, 3, 9))
    days = sorted({r["rate_date"] for r in rows})
    assert days == ["2025-03-03", "2025-03-04", "2025-03-05", "2025-03-06", "2025-03-07"]
    assert {r["currency"] for r in rows} == set(extract.FX_CURRENCIES)


def test_event_window_uses_lookback(settings):
    loader = LocalLoader(settings.landing_dir)
    start, end = datetime(2025, 6, 10, tzinfo=UTC), datetime(2025, 6, 11, tzinfo=UTC)
    n = load_app_events(settings, loader, "b1", start, end)
    rows = [json.loads(line) for f in (settings.landing_dir / "app_events").glob("*.ndjson")
            for line in f.read_text().splitlines()]
    assert n == len(rows) > 0
    assert min(r["received_at"] for r in rows) >= "2025-06-07"
    assert max(r["received_at"] for r in rows) < "2025-06-11"
    assert {r["_batch_id"] for r in rows} == {"b1"}


def test_full_refresh_replaces_previous_batches(settings):
    loader = LocalLoader(settings.landing_dir)
    start, end = datetime(2024, 10, 1, tzinfo=UTC), datetime(2026, 10, 4, tzinfo=UTC)
    first = load_app_events(settings, loader, "b1", start, end, full_refresh=True)
    second = load_app_events(settings, loader, "b2", start, end, full_refresh=True)
    assert first == second == loader.row_count("app_events")


def test_check_raw_tables_fails_on_missing_table(settings):
    loader = LocalLoader(settings.landing_dir)
    load_app_snapshots(settings, loader, "b1")
    with pytest.raises(RuntimeError, match="crm_companies"):
        check_raw_tables(loader)


def test_bigquery_loader_job_config():
    bigquery = pytest.importorskip("google.cloud.bigquery")
    from ingestion.load import BigQueryLoader

    calls = []

    class FakeClient:
        def load_table_from_file(self, fh, table_id, job_config):
            calls.append((fh.read(), table_id, job_config))
            return SimpleNamespace(result=lambda: None)

    loader = BigQueryLoader("proj", "raw", "US", partition=True, client=FakeClient())
    rows = [{"event_id": 1, "user_id": 2, "session_id": 3, "event_name": "signup",
             "event_ts": "2025-01-01 00:00:00", "received_at": "2025-01-01 00:00:01",
             "platform": "web", "app_version": None}]
    loader.load("app_events", rows, "b1")
    loader.load("app_events", rows, "b1", replace=True)
    body, table_id, cfg = calls[0]
    assert table_id == "proj.raw.app_events"
    assert cfg.write_disposition == bigquery.WriteDisposition.WRITE_APPEND
    assert cfg.time_partitioning.field == "received_at"
    assert calls[1][2].write_disposition == bigquery.WriteDisposition.WRITE_TRUNCATE
    assert json.loads(body)["_batch_id"] == "b1"

    sandbox = BigQueryLoader("proj", "raw", "US", partition=False, client=FakeClient())
    sandbox.load("app_events", rows, "b1")
    assert calls[-1][2].time_partitioning is None
