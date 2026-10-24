# Data sources

PulseBoard is a fictional B2B SaaS company selling a reporting and dashboard tool, publicly launched in
October 2024. Every source below is synthetic, produced by `data_generator/` with a fixed seed, and
covers **1 Oct 2024 to 30 Sep 2026**. The data is shaped to behave like the real systems a company
this size runs, quirks included.

| Source | Stands in for | Format | Location |
|---|---|---|---|
| App DB | The product's Postgres database | SQLite file | `data/raw/app_db/app.sqlite` |
| CRM | HubSpot / Salesforce companies API | Paginated JSON | `data/raw/crm/companies_page_*.json` |
| Ad spend | Monthly exports from ad platforms | CSV, one per month | `data/raw/marketing/ad_spend_YYYY_MM.csv` |
| FX rates | A daily exchange-rate API | JSON, one per month | `data/raw/fx/usd_rates_YYYY_MM.json` |

Default volumes (10,000 accounts): about 17k users, 1.5M events, 1.6k subscriptions, 6.4k invoices,
9.9k CRM records.

## App DB

| Table | Grain | Notes |
|---|---|---|
| `accounts` | one per workspace | No segment column: segment lives only in the CRM. |
| `users` | one per login | `role` is `owner` or `member`. `onboarding_flow` is set for owners. |
| `events` | one per tracked product event (raw log, no primary key) | Has `received_at` for incremental loads. |
| `subscriptions` | one per subscription version | A seat or plan change ends the row (`status = changed`) and starts a new one. |
| `invoices` | one per invoice attempt | Amounts are integers in **minor units** (cents, paise) of the local currency. |
| `experiment_assignments` | one per assigned owner | `onboarding_checklist_v1`, 50/50 control vs treatment. |

Event names: `signup`, `onboarding_completed`, `report_created`, `trial_started`, `invite_sent`,
`invite_accepted`, `session_start`, `view_dashboard`, `run_query`, `create_report`, `share_report`,
`export_data`. The first `report_created` marks activation; later reports are `create_report`.

## CRM

Each record looks like this:

```json
{"id": "30000123", "properties": {
  "name": "Summit Analytics LLC", "app_account_id": "1124", "segment": "Mid Market",
  "numberofemployees": 340, "industry": "Retail", "region": "EMEA", "country": "DE",
  "hubspot_owner": "d.muller", "lifecyclestage": "customer",
  "createdate": "2025-01-14T10:02:11.000Z", "lastmodifieddate": "2025-05-02T08:40:00.000Z"}}
```

Pages link to the next one through `paging.next.after`, like a real paginated API.

## Ad spend CSV

Columns: `Date, Platform, Campaign, Impressions, Clicks, Spend, Currency`. Platforms are Google Ads,
Meta Ads and LinkedIn Ads.

## FX feed

```json
{"amount": 1.0, "base": "USD", "start_date": "2025-01-02", "end_date": "2025-01-31",
 "rates": {"2025-01-02": {"EUR": 0.9187, "GBP": 0.7921, "AUD": 1.5203, "INR": 83.71}, "...": {}}}
```

Rates are units of currency per 1 USD. Divide a local amount by the rate to get USD.

## Known data quality issues

These are deliberate, and each one is handled in the dbt staging layer and covered by a test.

| # | Source | Issue | Handling |
|---|---|---|---|
| 1 | events | About 0.3% of rows are retried uploads with the **same `event_id`**. | Deduplicate on `event_id`, keep the earliest `received_at`. |
| 2 | events | About 0.1% of events have **no `user_id`** (anonymous or bot traffic). | Exclude from user metrics. |
| 3 | events | About 0.02% of events have an `event_ts` **a year in the future** (wrong device clocks). | Drop when `event_ts > received_at + 1 day`. |
| 4 | events | About 3% of mobile events **arrive 1 to 72 hours late**. | Incremental loads use `received_at` with a 3-day lookback window. |
| 5 | events | **iOS double-fire bug**, 20 to 22 Jan 2026: `session_start` logged twice with different ids. | Not deduplicable by id. DAU uses distinct users, so it isn't affected; an event-volume test flags the spike. |
| 6 | events | **Outage on 14 Jul 2025**: activity falls by about half. | Real, kept, annotated. |
| 7 | users | **Internal QA users** (`@pulseboard.io`, account 1000) are very active. | Excluded everywhere. |
| 8 | CRM | **Segment spelled inconsistently**: `SMB`, `smb`, `Small Business`, `Mid Market`, `MM`, `ENT`, trailing spaces... | Map to three canonical values. |
| 9 | CRM | About 1.5% of companies have **duplicate records**, sometimes with an updated segment. | Keep the latest `lastmodifieddate`. |
| 10 | CRM | About 2% of accounts are **missing from the CRM**; about 3% have no industry. | Segment and industry `Unknown`. |
| 11 | CRM | `app_account_id` is a **string**, while the App DB uses integers. | Cast in staging. |
| 12 | ad spend | **US date format** (`MM/DD/YYYY`) and **formatted numbers** (`"1,234.56"`). | Parse explicitly. |
| 13 | ad spend | Each monthly export **repeats the previous month's last day**. | Deduplicate on date + platform + campaign, keeping the later file. |
| 14 | ad spend | Platform names don't match app channel names. | Map: Google Ads to `paid_search`, Meta and LinkedIn to `paid_social`. |
| 15 | FX | **No rates on weekends**. | Forward-fill from the previous business day. |
| 16 | invoices | **Five currencies**, amounts in minor units. | Divide by 100, convert at the issue-date rate. |
| 17 | invoices | Declined cards produce a `failed` invoice followed by a `paid` retry. | Only `paid` counts as revenue; `refunded` and `failed` are excluded. |

## What's built into the behaviour

These patterns are what the analysis notebooks should be able to find.

- **Growth**: signups roughly triple over two years. Weekdays are busier than weekends; December and
  August are quiet.
- **Segments**: about 70% SMB, 22% Mid-Market, 8% Enterprise by count. Enterprise brings far more
  revenue per account and churns much less.
- **Funnel**: about 74% of owners complete onboarding, 44% activate, 27% start a trial, and 10% pay.
- **A/B test**: `onboarding_checklist_v1` raises activation. It is rolled out to everyone from 11 May 2026.
- **Churn**: driven by a hidden engagement score. Usage declines in the roughly 60 days before an
  account cancels, which is the signal a churn model can learn.
- **Expansion**: accounts add seats as they invite teammates, and small teams outgrow the Starter plan.
