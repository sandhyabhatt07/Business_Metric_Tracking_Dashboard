# Setup

There are two ways to run the pipeline. They use the same code and the same dbt models.

| | Local (DuckDB) | Cloud (BigQuery) |
|---|---|---|
| Needs | Python 3.12, or Docker | A Google account and Docker |
| Warehouse | `data/warehouse.duckdb`, a single file | Your BigQuery project |
| Good for | Trying it in 2 minutes, CI | The live dashboard |

## Local, without any cloud account

```bash
pip install -r requirements.txt -r docker/requirements-dbt.txt
make data        # generate the sources (about 20 seconds)
make warehouse   # load them into data/warehouse.duckdb
make dbt         # build every model and run every test
```

Or run the same thing in Airflow: `docker compose up --build`, open <http://localhost:8080>, and turn on
the `metrics_pipeline` DAG. With no `.env` file it uses DuckDB.

## BigQuery

About 15 minutes the first time. No credit card is needed.

### 1. Create a project (free sandbox)

1. Open the [Google Cloud console](https://console.cloud.google.com/) and create a project, for example
   `metrics-portfolio`. Note the **project id**; it may differ from the name.
2. Open **BigQuery** in that project. Without a billing account it runs as the
   [BigQuery sandbox](https://cloud.google.com/bigquery/docs/sandbox): free, with 10 GB of storage and
   1 TB of queries a month. This project uses well under 1 GB.

**Sandbox limits that matter here.** Tables expire 60 days after they're created; re-run the pipeline to
recreate them. Partitions older than 60 days are dropped, which is why `BQ_SANDBOX=true` keeps the big
tables unpartitioned. If you add a billing account later (still free at this size), set
`BQ_SANDBOX=false` and remove the default table expiration on the datasets.

### 2. Create a service account key

1. In the console, go to **IAM and Admin, then Service Accounts**, and create one called `metrics-pipeline`.
2. Grant it the roles **BigQuery Data Editor** and **BigQuery Job User**.
3. Open the account, then **Keys, Add key, Create new key, JSON**. Save the file as
   `secrets/gcp-key.json` in this repo. The `secrets/` folder is git-ignored; never commit the key.

### 3. Configure and run

```bash
cp .env.example .env    # then set GCP_PROJECT to your project id
docker compose up --build
```

Open <http://localhost:8080>; this local setup has no login. Turn on the `metrics_pipeline` DAG. The
first run generates the sources if needed, backfills two years of history into the `raw` dataset, then
runs dbt. That takes a few minutes. Later daily runs load only newly received events. To reload
everything, trigger the DAG with `full_refresh` set to true.

Without Docker: `make data load-bigquery dbt-bigquery`, with `GCP_PROJECT` and
`GOOGLE_APPLICATION_CREDENTIALS=secrets/gcp-key.json` set in your shell.

### Datasets you'll see

| Dataset | Contents |
|---|---|
| `raw` | Source tables as loaded (see below) |
| `reference` | dbt seeds: segment spellings, ad platform to channel, plans |
| `staging` | One cleaned view per source table |
| `intermediate` | FX rates per day, account funnel, account-month MRR |
| `core` | The star schema: facts and dimensions |
| `metrics` | Dashboard-ready KPI tables |

## Raw tables

| Table | Load | Notes |
|---|---|---|
| `app_accounts`, `app_users`, `app_subscriptions`, `app_invoices`, `app_experiment_assignments` | full reload each run | Typed as in the App DB |
| `app_events` | append by `received_at`, with a 3-day lookback | Overlaps on purpose; staging deduplicates. Partitioned by `received_at` outside the sandbox. |
| `crm_companies` | full reload | All text, plus the original JSON record in `_raw` |
| `ad_spend` | full reload | All text, plus `_source_file` and `_source_line` |
| `fx_rates` | full reload | All text |

Every row carries `_batch_id` (the Airflow run) and `_loaded_at`.
