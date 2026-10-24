# Leadership metrics dashboard

One dashboard, two builds: **Power BI** (the main version, for analyst-role portfolios) and
**Looker Studio** (a lighter version with a public live link). Both read only the `metrics` tables and
`ml.churn_risk_scores`, so every number matches the [metrics spec](../docs/metrics_spec.md) and the
notebooks.

| File | What it is |
|---|---|
| [powerbi_guide.md](powerbi_guide.md) | Step-by-step build: connect, model, measures, pages |
| [measures.dax](measures.dax) | Every DAX measure, ready to paste |
| [pulseboard_theme.json](pulseboard_theme.json) | Power BI theme (colours, fonts) |
| [looker_studio_guide.md](looker_studio_guide.md) | Step-by-step build for Looker Studio |
| `screenshots/` | Add your screenshots here once built; the main README links them |

## Data sources

| Option | Power BI | Looker Studio |
|---|---|---|
| BigQuery (recommended) | Get Data, Google BigQuery | Add data, BigQuery |
| No cloud account | `python -m analysis.export_marts`, then Get Data, Text/CSV from `data/exports/` | Upload the CSVs to Google Sheets, then Add data, Google Sheets |

## Pages

Every page has the same slicers across the top: **date range** and **segment**.

### 1. Executive overview

The one-screen answer to "how are we doing?".

```
+-----------+-----------+-----------+-----------+-----------+-----------+
|   MRR     | MRR MoM % |  DAU      | Stickiness|   NRR     | Activation|
+-----------+-----------+-----------+-----------+-----------+-----------+
| MRR by segment, monthly (stacked area)| DAU, daily, with 7-day avg     |
|                                       | annotate 14 Jul 2025 outage    |
+---------------------------------------+--------------------------------+
| Net new MRR by month (columns)        | Funnel: signup > paid (mature) |
+---------------------------------------+--------------------------------+
```

### 2. Revenue

- MRR movements by month: stacked columns of new, expansion, reactivation (up) and contraction,
  churned (down), with net new MRR as a line.
- MRR vs billed revenue by month (two lines), with a note on why they differ (annual plans bill upfront).
- NRR, GRR and logo retention by segment (clustered bars, latest month) and NRR over time (line).
- Table: segment, MRR, paying accounts, ARPA, NRR.

### 3. Product engagement

- DAU, WAU, MAU (lines) and stickiness (DAU/MAU).
- Retention matrix: signup month (rows) by week 0 to 26 (columns), conditional formatting on retention %.
- Week 4 retention by segment.

### 4. Growth and acquisition

- Funnel (signup, onboarded, activated, trial, paid) for mature cohorts, sliceable by channel.
- Activation rate by signup month, with the A/B test window shaded and the rollout date marked.
- A/B test result: activation by variant (bar with the two rates).
- Signups, spend and CAC by channel per month.

### 5. Customer risk

- Cards: expected MRR at risk (60 days), high-risk accounts, high-risk MRR.
- Table of high-risk accounts sorted by expected MRR at risk: account, segment, MRR, churn probability,
  usage trend, days since last active, months to renewal.
- Note on the page: scores rank risk; they aren't a revenue forecast (see the churn notebook).

## Design rules

- Colours: SMB `#8a8f98` (grey), Mid-Market `#2f6fdb` (blue), Enterprise `#0b8a5f` (green), Unknown
  `#c9ccd1`. Same colours on every page and in the notebooks.
- Every visual title says what it shows and the unit, for example "MRR by segment (USD, month end)".
- A small "Definitions" text box on each page links to the metrics spec.
- Data as of 30 Sep 2026: show it in the header so nobody mistakes the data for live numbers.
