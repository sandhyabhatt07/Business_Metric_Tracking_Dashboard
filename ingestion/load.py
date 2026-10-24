"""Loaders: write extracted rows to BigQuery, a local DuckDB warehouse, or NDJSON files.

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


DUCKDB_TYPES = {"INT64": "BIGINT", "STRING": "VARCHAR", "TIMESTAMP": "TIMESTAMP", "FLOAT64": "DOUBLE"}


class DuckDBLoader:
    """A local stand-in for BigQuery: same raw tables, in the `raw` schema of a DuckDB file."""

    def __init__(self, path: Path, schema: str = "raw"):
        import duckdb

        self.duckdb = duckdb
        self.path = path
        self.schema = schema
        path.parent.mkdir(parents=True, exist_ok=True)
        with duckdb.connect(str(path)) as con:
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    def load(self, table_name: str, rows: list[dict], batch_id: str, replace: bool | None = None) -> int:
        import tempfile

        table = RAW_TABLES[table_name]
        replace = table.mode == "replace" if replace is None else replace
        cols = {name: DUCKDB_TYPES[typ] for name, typ in table.all_columns}
        ddl = ", ".join(f'"{c}" {t}' for c, t in cols.items())
        target = f"{self.schema}.{table.name}"
        # A temporary directory rather than an open temp file, so DuckDB can read it on Windows too.
        with tempfile.TemporaryDirectory() as tmp, self.duckdb.connect(str(self.path)) as con:
            batch_file = Path(tmp) / f"{table.name}.ndjson"
            batch_file.write_bytes(to_ndjson(rows, table, batch_id))
            con.execute(f"CREATE {'OR REPLACE ' if replace else ''}TABLE "
                        f"{'' if replace else 'IF NOT EXISTS '}{target} ({ddl})")
            if rows:
                columns = "{" + ", ".join(f"'{c}': '{t}'" for c, t in cols.items()) + "}"
                con.execute(f"INSERT INTO {target} SELECT * FROM read_json('{batch_file.as_posix()}', "
                            f"format = 'newline_delimited', columns = {columns})")
        return len(rows)

    def row_count(self, table_name: str) -> int:
        with self.duckdb.connect(str(self.path)) as con:
            exists = con.execute("SELECT count(*) FROM information_schema.tables "
                                 "WHERE table_schema = ? AND table_name = ?", [self.schema, table_name]).fetchone()[0]
            return con.execute(f"SELECT count(*) FROM {self.schema}.{table_name}").fetchone()[0] if exists else 0


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
