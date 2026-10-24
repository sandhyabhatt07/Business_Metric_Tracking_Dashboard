"""Daily pipeline: sources -> raw tables -> dbt models and tests.

The first run backfills the two years of history (so does triggering with `full_refresh = true`).
Later runs load only the events received in their data interval, plus fresh snapshots of the small tables.

PIPELINE_TARGET picks the warehouse: `bigquery`, or `duckdb` for a local file that needs no cloud account.
"""

import os
from datetime import datetime, timedelta, timezone

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import Param, chain, dag, get_current_context, task

HISTORY_START = datetime(2024, 10, 1, tzinfo=timezone.utc)
TARGET = os.getenv("PIPELINE_TARGET", "duckdb")
DBT_BIN = os.getenv("DBT_BIN", "dbt")
DBT_DIR = os.getenv("DBT_PROJECT_DIR", "/opt/project/transform")


def _context():
    """Settings, loader and a batch id for the current run. Imported lazily to keep DAG parsing fast."""
    from ingestion.run import make_loader
    from ingestion.settings import Settings

    ctx = get_current_context()
    settings = Settings.from_env()
    batch_id = ctx["run_id"].replace(":", "").replace("+", "_")
    return ctx, settings, make_loader(settings, TARGET), batch_id


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

    dbt_build = BashOperator(
        task_id="dbt_build",
        doc_md="Run every dbt model, seed, snapshot and test. Any failing test fails the run.",
        bash_command=f"cd {DBT_DIR} && {DBT_BIN} deps --quiet && {DBT_BIN} build --target {TARGET}",
        env={"DBT_PROFILES_DIR": DBT_DIR},
        append_env=True,
    )

    loads = [load_app_snapshots(), load_app_events(), load_crm(), load_ad_spend(), load_fx()]
    if TARGET == "duckdb":
        # DuckDB allows one writer at a time, so load sequentially.
        chain(ensure_sources(), *loads, check_raw_tables(), dbt_build)
    else:
        chain(ensure_sources(), loads, check_raw_tables(), dbt_build)


metrics_pipeline()
