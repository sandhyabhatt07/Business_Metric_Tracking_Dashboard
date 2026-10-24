"""Loaders: write extracted rows to BigQuery, or to local NDJSON files for a dry run.

BigQuery loads use load jobs (not streaming or DML), so they also work in the free BigQuery sandbox.
"""

import io
import json
from datetime import datetime, timezone
from pathlib import Path

from .schemas import RAW_TABLES, RawTable


def with_load_columns(rows: list[dict], batch_id: str, loaded_at: datetime) -> list[dict]:
    stamp = loaded_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return [{**r, "_batch_id": batch_id, "_loaded_at": stamp} for r in rows]


def to_ndjson(rows: list[dict], table: RawTable, batch_id: str) -> bytes:
    rows = with_load_columns(rows, batch_id, datetime.now(timezone.utc))
    names = [c for c, _ in table.all_columns]
    unknown = set().union(*(r.keys() for r in rows)) - set(names) if rows else set()
    if unknown:
        raise ValueError(f"{table.name}: columns not in schema: {sorted(unknown)}")
    buf = io.StringIO()
    for r in rows:
        buf.write(json.dumps({c: r.get(c) for c in names}, separators=(",", ":")))
        buf.write("\n")
    return buf.getvalue().encode()


class LocalLoader:
    """Writes each batch to <landing_dir>/<table>/<batch_id>.ndjson. Useful without a GCP account."""

    def __init__(self, landing_dir: Path):
        self.landing_dir = landing_dir

    def load(self, table_name: str, rows: list[dict], batch_id: str, replace: bool | None = None) -> int:
        table = RAW_TABLES[table_name]
        folder = self.landing_dir / table.name
        if (table.mode == "replace" if replace is None else replace) and folder.exists():
            for old in folder.glob("*.ndjson"):
                old.unlink()
        folder.mkdir(parents=True, exist_ok=True)
        part = len(list(folder.glob(f"{batch_id}*.ndjson")))
        (folder / f"{batch_id}{f'_{part}' if part else ''}.ndjson").write_bytes(to_ndjson(rows, table, batch_id))
        return len(rows)

    def row_count(self, table_name: str) -> int:
        folder = self.landing_dir / table_name
        return sum(f.read_bytes().count(b"\n") for f in folder.glob("*.ndjson")) if folder.exists() else 0


class BigQueryLoader:
    def __init__(self, project: str, dataset: str, location: str, partition: bool = True, client=None):
        """Set `partition=False` in the BigQuery sandbox, which expires partitions older than 60 days."""
        from google.cloud import bigquery

        self.bq = bigquery
        self.client = client or bigquery.Client(project=project, location=location)
        self.dataset = f"{project}.{dataset}"
        self.location = location
        self.partition = partition

    def ensure_dataset(self) -> None:
        ds = self.bq.Dataset(self.dataset)
        ds.location = self.location
        self.client.create_dataset(ds, exists_ok=True)

    def load(self, table_name: str, rows: list[dict], batch_id: str, replace: bool | None = None) -> int:
        """`replace` overrides the table's default mode, e.g. to truncate before an events backfill."""
        table = RAW_TABLES[table_name]
        bq = self.bq
        replace = table.mode == "replace" if replace is None else replace
        cfg = bq.LoadJobConfig(
            source_format=bq.SourceFormat.NEWLINE_DELIMITED_JSON,
            schema=[bq.SchemaField(name, typ) for name, typ in table.all_columns],
            write_disposition=(bq.WriteDisposition.WRITE_TRUNCATE if replace
                               else bq.WriteDisposition.WRITE_APPEND),
            create_disposition=bq.CreateDisposition.CREATE_IF_NEEDED,
        )
        if table.partition_by and self.partition:
            cfg.time_partitioning = bq.TimePartitioning(type_=bq.TimePartitioningType.DAY,
                                                        field=table.partition_by)
        if table.cluster_by:
            cfg.clustering_fields = table.cluster_by
        job = self.client.load_table_from_file(io.BytesIO(to_ndjson(rows, table, batch_id)),
                                               f"{self.dataset}.{table.name}", job_config=cfg)
        job.result()
        return len(rows)

    def row_count(self, table_name: str) -> int:
        from google.api_core.exceptions import NotFound

        try:
            return self.client.get_table(f"{self.dataset}.{table_name}").num_rows
        except NotFound:
            return 0
