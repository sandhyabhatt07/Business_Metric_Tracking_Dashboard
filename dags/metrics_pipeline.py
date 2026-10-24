"""Daily pipeline: sources -> BigQuery raw -> (dbt models, added in step 3).

The first run backfills the two years of history (so does triggering with `full_refresh = true`).
Later runs load only the events received in their data interval, plus fresh snapshots of the small tables.
Set PIPELINE_DRY_RUN=true to write NDJSON files to LANDING_DIR instead of BigQuery.
"""

import os
from datetime import datetime, timedelta, timezone

from airflow.sdk import Param, dag, get_current_context, task

HISTORY_START = datetime(2024, 10, 1, tzinfo=timezone.utc)
DRY_RUN = os.getenv("PIPELINE_DRY_RUN", "false").lower() in ("1", "true", "yes")


def _context():
    """Settings, loader and a batch id for the current run. Imported lazily to keep DAG parsing fast."""
    from ingestion.run import make_loader
    from ingestion.settings import Settings

    ctx = get_current_context()
    settings = Settings.from_env()
    batch_id = ctx["run_id"].replace(":", "").replace("+", "_")
    return ctx, settings, make_loader(settings, DRY_RUN), batch_id


def _interval(ctx) -> tuple[datetime, datetime]:
    """The run's data interval. Manual runs in Airflow 3 have none, so they cover the last day."""
    end = ctx.get("data_interval_end") or datetime.now(timezone.utc)
    return ctx.get("data_interval_start") or end - timedelta(days=1), end


def _window(ctx) -> tuple[datetime, datetime, bool]:
    start, end = _interval(ctx)
    if ctx["params"]["full_refresh"]:
        return HISTORY_START, end + timedelta(days=1), True
    return start, end, False


@dag(
    dag_id="metrics_pipeline",
    schedule="@daily",
    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
    params={"full_refresh": Param(False, type="boolean",
                                  description="Truncate and reload all events from the start of history")},
    tags=["metrics", "bigquery"],
    doc_md=__doc__,
)
def metrics_pipeline():

    @task
    def ensure_sources() -> str:
        """The demo's 'source systems' are generated files. Build them if they aren't there yet."""
        from pathlib import Path

        from data_generator.config import Config
        from data_generator.generate import build, write_all

        out = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
        if not (out / "app_db" / "app.sqlite").exists():
            write_all(Config(), out, build(Config()))
        return str(out)

    @task
    def load_app_snapshots() -> dict:
        from ingestion.run import load_app_snapshots as run

        _, settings, loader, batch_id = _context()
        return run(settings, loader, batch_id)

    @task
    def load_app_events() -> int:
        from ingestion.run import load_app_events as run

        ctx, settings, loader, batch_id = _context()
        start, end, full = _window(ctx)
        if not full and loader.row_count("app_events") == 0:
            # First run against an empty warehouse: backfill instead of loading one empty day.
            start, end, full = HISTORY_START, end + timedelta(days=1), True
        return run(settings, loader, batch_id, start, end, full_refresh=full)

    @task
    def load_crm() -> int:
        from ingestion.run import load_crm as run

        _, settings, loader, batch_id = _context()
        return run(settings, loader, batch_id)

    @task
    def load_ad_spend() -> int:
        from ingestion.run import load_ad_spend as run

        _, settings, loader, batch_id = _context()
        return run(settings, loader, batch_id)

    @task
    def load_fx() -> int:
        from ingestion.run import load_fx as run

        ctx, settings, loader, batch_id = _context()
        # FX is tiny: always reload the whole history so weekend forward-fills stay consistent.
        return run(settings, loader, batch_id, HISTORY_START.date(), _interval(ctx)[1].date())

    @task
    def check_raw_tables() -> dict:
        from ingestion.run import check_raw_tables as run

        _, _, loader, _ = _context()
        return run(loader)

    sources = ensure_sources()
    loads = [load_app_snapshots(), load_app_events(), load_crm(), load_ad_spend(), load_fx()]
    sources >> loads >> check_raw_tables()


metrics_pipeline()
