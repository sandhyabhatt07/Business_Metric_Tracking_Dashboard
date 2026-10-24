# Setup: BigQuery and Airflow

About 15 minutes the first time. You need Docker Desktop and a Google account. No credit card is needed.

## 1. Create a BigQuery project (free sandbox)

1. Open the [Google Cloud console](https://console.cloud.google.com/) and create a project, for example
   `metrics-portfolio`. Note the **project id**; it may differ from the name.
2. Open **BigQuery** in that project. Without a billing account it runs as the
   [BigQuery sandbox](https://cloud.google.com/bigquery/docs/sandbox): free, with 10 GB of storage and
   1 TB of queries a month. This project uses well under 1 GB.

**Sandbox limits that matter here.** Tables expire 60 days after they're created; re-run the pipeline to
recreate them. Partitions older than 60 days are dropped, which is why `BQ_SANDBOX=true` keeps the raw
events table unpartitioned. If you add a billing account later (still free at this size), set
`BQ_SANDBOX=false` and remove the default table expiration on the datasets.

## 2. Create a service account key

1. In the console, go to **IAM and Admin, then Service Accounts**, and create one called `metrics-pipeline`.
2. Grant it the roles **BigQuery Data Editor** and **BigQuery Job User**.
3. Open the account, then **Keys, Add key, Create new key, JSON**. Save the file as
   `secrets/gcp-key.json` in this repo. The `secrets/` folder is git-ignored; never commit the key.

## 3. Configure

```bash
cp .env.example .env
# edit .env: set GCP_PROJECT to your project id
```

## 4. Run Airflow

```bash
docker compose up --build
```

Open <http://localhost:8080>; this local setup has no login. Turn on the `metrics_pipeline` DAG. Its first
run generates the source data if needed, then backfills two years of history into the `raw` dataset.
That takes a few minutes. Later daily runs load only newly received events and refresh the small tables.
To reload everything, trigger the DAG with `full_refresh` set to true.

## Without Docker or GCP

```bash
pip install -r requirements.txt
make data
make load-dry-run   # same loads, written as NDJSON files under data/landing/
make load           # into BigQuery, using GCP_PROJECT and GOOGLE_APPLICATION_CREDENTIALS
```

## Raw tables

| Table | Load | Notes |
|---|---|---|
| `app_accounts`, `app_users`, `app_subscriptions`, `app_invoices`, `app_experiment_assignments` | full reload each run | Typed as in the App DB |
| `app_events` | append by `received_at`, with a 3-day lookback | Overlaps on purpose; staging deduplicates. Partitioned by `received_at` outside the sandbox. |
| `crm_companies` | full reload | All text, plus the original JSON record in `_raw` |
| `ad_spend` | full reload | All text, plus `_source_file` and `_source_line` |
| `fx_rates` | full reload | All text |

Every row carries `_batch_id` (the Airflow run) and `_loaded_at`.
