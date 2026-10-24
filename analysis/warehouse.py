"""Read from (and write back to) the warehouse from notebooks.

Uses the local DuckDB file by default; set WAREHOUSE=bigquery (with GCP_PROJECT and
GOOGLE_APPLICATION_CREDENTIALS) to read the same tables from BigQuery.
"""

import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = os.getenv("WAREHOUSE", "duckdb")
DUCKDB_PATH = Path(os.getenv("DUCKDB_PATH", ROOT / "data" / "warehouse.duckdb"))


def table(name: str, columns: str = "*", where: str | None = None) -> pd.DataFrame:
    """Read `schema.table`, e.g. table("core.dim_account")."""
    sql = f"select {columns} from {_qualify(name)}" + (f" where {where}" if where else "")
    return query(sql)


def query(sql: str) -> pd.DataFrame:
    if WAREHOUSE == "bigquery":
        from google.cloud import bigquery

        return bigquery.Client(project=os.environ["GCP_PROJECT"]).query(sql).to_dataframe()
    import duckdb

    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as con:
        return con.sql(sql).df()


def write(df: pd.DataFrame, name: str) -> None:
    """Replace `schema.table` with a DataFrame, e.g. model scores for the dashboard."""
    schema, tbl = name.split(".")
    if WAREHOUSE == "bigquery":
        from google.cloud import bigquery

        client = bigquery.Client(project=os.environ["GCP_PROJECT"])
        client.create_dataset(schema, exists_ok=True)
        job = client.load_table_from_dataframe(
            df, f"{client.project}.{name}",
            job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE"))
        job.result()
        return
    import duckdb

    with duckdb.connect(str(DUCKDB_PATH)) as con:
        con.execute(f"create schema if not exists {schema}")
        con.register("df_to_write", df)
        con.execute(f"create or replace table {schema}.{tbl} as select * from df_to_write")


def _qualify(name: str) -> str:
    if WAREHOUSE == "bigquery":
        return f"`{os.environ['GCP_PROJECT']}.{name}`"
    return name
