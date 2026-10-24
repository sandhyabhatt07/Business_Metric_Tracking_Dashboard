from pathlib import Path

import pytest


LOADS = ["load_app_snapshots", "load_app_events", "load_crm", "load_ad_spend", "load_fx"]


def _dag(monkeypatch, target):
    pytest.importorskip("airflow")
    from airflow.dag_processing.dagbag import DagBag

    monkeypatch.setenv("PIPELINE_TARGET", target)
    bag = DagBag(dag_folder=str(Path(__file__).parents[1] / "dags"), include_examples=False)
    assert not bag.import_errors
    return bag.dags["metrics_pipeline"]


def test_bigquery_loads_run_in_parallel(monkeypatch):
    dag = _dag(monkeypatch, "bigquery")
    assert dag.get_task("ensure_sources").downstream_task_ids == set(LOADS)
    for t in LOADS:
        assert dag.get_task(t).downstream_task_ids == {"check_raw_tables"}
    assert dag.get_task("check_raw_tables").downstream_task_ids == {"dbt_build"}
    assert "--target bigquery" in dag.get_task("dbt_build").bash_command


def test_duckdb_loads_run_one_at_a_time(monkeypatch):
    dag = _dag(monkeypatch, "duckdb")
    order = ["ensure_sources", *LOADS, "check_raw_tables", "dbt_build"]
    for upstream, downstream in zip(order, order[1:]):
        assert dag.get_task(upstream).downstream_task_ids == {downstream}
