from pathlib import Path

import pytest


def test_dag_imports_and_wires_tasks():
    pytest.importorskip("airflow")
    from airflow.dag_processing.dagbag import DagBag

    bag = DagBag(dag_folder=str(Path(__file__).parents[1] / "dags"), include_examples=False)
    assert not bag.import_errors
    dag = bag.dags["metrics_pipeline"]
    loads = {"load_app_snapshots", "load_app_events", "load_crm", "load_ad_spend", "load_fx"}
    assert dag.get_task("ensure_sources").downstream_task_ids == loads
    for t in loads:
        assert dag.get_task(t).downstream_task_ids == {"check_raw_tables"}
