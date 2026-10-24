"""Pipeline settings, read from environment variables (see .env.example)."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    # Where raw tables go: "bigquery", "duckdb" (local warehouse file) or "files" (NDJSON, inspection only).
    target: str
    gcp_project: str | None
    bq_location: str
    raw_dataset: str
    # The free BigQuery sandbox drops partitions older than 60 days, so raw events stay unpartitioned there.
    bq_sandbox: bool
    data_dir: Path
    landing_dir: Path
    duckdb_path: Path
    # Either a local folder of saved API pages or an http(s) base URL.
    crm_source: str
    fx_source: str
    # How far back each incremental event load re-reads, to catch late mobile events.
    events_lookback_days: int

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
        return cls(
            target=os.getenv("PIPELINE_TARGET", "bigquery"),
            gcp_project=os.getenv("GCP_PROJECT"),
            bq_location=os.getenv("BQ_LOCATION", "US"),
            raw_dataset=os.getenv("BQ_RAW_DATASET", "raw"),
            bq_sandbox=os.getenv("BQ_SANDBOX", "true").lower() in ("1", "true", "yes"),
            data_dir=data_dir,
            landing_dir=Path(os.getenv("LANDING_DIR", "data/landing")),
            duckdb_path=Path(os.getenv("DUCKDB_PATH", "data/warehouse.duckdb")),
            crm_source=os.getenv("CRM_SOURCE", str(data_dir / "crm")),
            fx_source=os.getenv("FX_SOURCE", str(data_dir / "fx")),
            events_lookback_days=int(os.getenv("EVENTS_LOOKBACK_DAYS", "3")),
        )
