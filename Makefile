.PHONY: install data data-small warehouse dbt load-bigquery dbt-bigquery airflow test

export DUCKDB_PATH := $(CURDIR)/data/warehouse.duckdb
export DBT_PROFILES_DIR := $(CURDIR)/transform

install:
	pip install -r requirements.txt -r docker/requirements-dbt.txt

data:
	python -m data_generator.generate --out data/raw

data-small:
	python -m data_generator.generate --out data/raw --accounts 500

# Local warehouse: load raw tables into DuckDB, then build every model and test.
warehouse:
	python -m ingestion.run all --full-refresh --target duckdb

dbt:
	cd transform && dbt deps --quiet && dbt build --target duckdb

# BigQuery: needs GCP_PROJECT and GOOGLE_APPLICATION_CREDENTIALS (see docs/setup.md).
load-bigquery:
	python -m ingestion.run all --full-refresh --target bigquery

dbt-bigquery:
	cd transform && dbt deps --quiet && dbt build --target bigquery

airflow:
	docker compose up --build

test:
	python -m pytest -q
