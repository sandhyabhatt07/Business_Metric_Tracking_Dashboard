"""Extract-and-load jobs. Airflow calls these functions; the CLI runs them by hand.

    python -m ingestion.run all --full-refresh            # backfill everything into BigQuery
    python -m ingestion.run all --full-refresh --dry-run  # same, written to data/landing/ instead
    python -m ingestion.run events --start 2026-09-29 --end 2026-09-30
"""

import argparse
import logging
from datetime import date, datetime, timedelta, timezone

from . import extract
from .load import BigQueryLoader, LocalLoader
from .schemas import RAW_TABLES
from .settings import Settings

log = logging.getLogger(__name__)
SNAPSHOT_TABLES = [t for t in extract.APP_TABLES if t != "events"]


def make_loader(settings: Settings, dry_run: bool):
    if dry_run:
        return LocalLoader(settings.landing_dir)
    if not settings.gcp_project:
        raise SystemExit("GCP_PROJECT is not set. Use --dry-run to write local files instead.")
    loader = BigQueryLoader(settings.gcp_project, settings.raw_dataset, settings.bq_location,
                            partition=not settings.bq_sandbox)
    loader.ensure_dataset()
    return loader


def load_app_snapshots(settings: Settings, loader, batch_id: str) -> dict[str, int]:
    """Small App DB tables are reloaded in full every run."""
    db = settings.data_dir / "app_db" / "app.sqlite"
    return {f"app_{t}": loader.load(f"app_{t}", extract.extract_app_table(db, t), batch_id)
            for t in SNAPSHOT_TABLES}


def load_app_events(settings: Settings, loader, batch_id: str, start: datetime, end: datetime,
                    full_refresh: bool = False) -> int:
    """Append events received in [start - lookback, end). Re-reads overlap on purpose; staging dedups.

    A full refresh truncates the table and reloads month by month to keep memory flat.
    """
    db = settings.data_dir / "app_db" / "app.sqlite"
    if not full_refresh:
        rows = extract.extract_app_table(db, "events", start - timedelta(days=settings.events_lookback_days), end)
        return loader.load("app_events", rows, batch_id)

    total, first = 0, True
    lo = start
    while lo < end:
        hi = min(datetime(lo.year + (lo.month == 12), lo.month % 12 + 1, 1, tzinfo=timezone.utc), end)
        rows = extract.extract_app_table(db, "events", lo, hi)
        total += loader.load("app_events", rows, batch_id, replace=first)
        log.info("events %s..%s: %s rows", lo.date(), hi.date(), len(rows))
        first, lo = False, hi
    return total


def load_crm(settings: Settings, loader, batch_id: str) -> int:
    return loader.load("crm_companies", extract.extract_crm(settings.crm_source), batch_id)


def load_ad_spend(settings: Settings, loader, batch_id: str) -> int:
    return loader.load("ad_spend", extract.extract_ad_spend(settings.data_dir / "marketing"), batch_id)


def load_fx(settings: Settings, loader, batch_id: str, start: date, end: date) -> int:
    return loader.load("fx_rates", extract.extract_fx(settings.fx_source, start, end), batch_id)


def check_raw_tables(loader) -> dict[str, int]:
    """Fail loudly if any raw table is missing or empty after the loads."""
    counts = {name: loader.row_count(name) for name in RAW_TABLES}
    empty = [name for name, n in counts.items() if n == 0]
    if empty:
        raise RuntimeError(f"raw tables missing or empty: {', '.join(empty)}")
    return counts


def _day(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("job", choices=["all", "app", "events", "crm", "ad_spend", "fx"])
    p.add_argument("--start", default="2024-10-01", help="first day (UTC) for events and FX")
    p.add_argument("--end", default="2026-10-04",
                   help="day after the last day (UTC); a few days past the data so late events land")
    p.add_argument("--full-refresh", action="store_true", help="truncate and reload events")
    p.add_argument("--dry-run", action="store_true", help="write NDJSON to LANDING_DIR instead of BigQuery")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    settings = Settings.from_env()
    loader = make_loader(settings, args.dry_run)
    batch_id = "manual_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    start, end = _day(args.start), _day(args.end)

    counts = {}
    if args.job in ("all", "app"):
        counts |= load_app_snapshots(settings, loader, batch_id)
    if args.job in ("all", "app", "events"):
        counts["app_events"] = load_app_events(settings, loader, batch_id, start, end, args.full_refresh)
    if args.job in ("all", "crm"):
        counts["crm_companies"] = load_crm(settings, loader, batch_id)
    if args.job in ("all", "ad_spend"):
        counts["ad_spend"] = load_ad_spend(settings, loader, batch_id)
    if args.job in ("all", "fx"):
        counts["fx_rates"] = load_fx(settings, loader, batch_id, start.date(), (end - timedelta(days=1)).date())
    for table, n in counts.items():
        log.info("%-28s %10s rows", table, f"{n:,}")


if __name__ == "__main__":
    main()
