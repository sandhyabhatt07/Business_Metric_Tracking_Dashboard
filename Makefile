.PHONY: install data data-small load load-dry-run airflow test

install:
	pip install -r requirements.txt

data:
	python -m data_generator.generate --out data/raw

data-small:
	python -m data_generator.generate --out data/raw --accounts 500

load:
	python -m ingestion.run all --full-refresh

load-dry-run:
	python -m ingestion.run all --full-refresh --dry-run

airflow:
	docker compose up --build

test:
	python -m pytest -q
