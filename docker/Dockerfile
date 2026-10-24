FROM apache/airflow:3.2.2-python3.12

# Pipeline dependencies, pinned to Airflow's tested constraint set.
COPY requirements-pipeline.txt /tmp/requirements-pipeline.txt
RUN pip install --no-cache-dir -r /tmp/requirements-pipeline.txt \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.2.2/constraints-3.12.txt"

# dbt lives in its own virtualenv so its dependencies can't clash with Airflow's.
COPY requirements-dbt.txt /tmp/requirements-dbt.txt
RUN python -m venv /home/airflow/dbt-venv \
    && /home/airflow/dbt-venv/bin/pip install --no-cache-dir -r /tmp/requirements-dbt.txt
ENV DBT_BIN=/home/airflow/dbt-venv/bin/dbt
