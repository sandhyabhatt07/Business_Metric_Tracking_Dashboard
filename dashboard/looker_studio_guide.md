# Build the dashboard in Looker Studio

About 30 minutes. A lighter version of the Power BI dashboard (three pages) that anyone can open from a
link. You need a Google account and, ideally, the BigQuery project from [docs/setup.md](../docs/setup.md).

## 1. Connect the data

Go to [lookerstudio.google.com](https://lookerstudio.google.com), create a blank report, and add these
data sources. Choose **BigQuery**, then your project, the `metrics` dataset, and the table:

- `kpi_daily_active_users`
- `kpi_revenue_by_segment`
- `kpi_revenue_retention`
- `kpi_funnel_by_cohort`
- `kpi_user_retention_cohorts`

No BigQuery? Run `python -m analysis.export_marts`, upload the CSVs from `data/exports/` to one Google
Sheet (one tab each), and use the **Google Sheets** connector instead.

In each data source, check that `date_day`, `month_start` and `signup_week` are type **Date**.

## 2. Calculated fields

Add these in the data source (Resource, Manage added data sources, Edit, Add a field). They mirror the
DAX measures, so both dashboards show the same numbers.

| Data source | Field | Formula |
|---|---|---|
| `kpi_daily_active_users` | DAU (daily average) | `SUM(dau) / COUNT_DISTINCT(date_day)` |
| `kpi_daily_active_users` | Stickiness | `SUM(dau) / SUM(mau)` |
| `kpi_revenue_by_segment` | Net new MRR | `SUM(new_mrr_usd) + SUM(expansion_mrr_usd) + SUM(reactivation_mrr_usd) - SUM(contraction_mrr_usd) - SUM(churned_mrr_usd)` |
| `kpi_revenue_by_segment` | ARPA | `SUM(mrr_usd) / SUM(paying_accounts)` |
| `kpi_revenue_retention` | NRR | `SUM(net_retained_mrr_usd) / SUM(mrr_12m_ago_usd)` |
| `kpi_revenue_retention` | GRR | `SUM(gross_retained_mrr_usd) / SUM(mrr_12m_ago_usd)` |
| `kpi_funnel_by_cohort` | Activation rate | `SUM(activated) / SUM(signups)` |
| `kpi_funnel_by_cohort` | Signup to paid | `SUM(paid) / SUM(signups)` |
| `kpi_user_retention_cohorts` | Retention | `SUM(active_users) / SUM(cohort_users)` |

Set the rates to type Percent.

**Filters that make the numbers correct.** Create two filters (Resource, Manage filters) and apply them
to the visuals noted below:

- *Mature cohorts*: include `is_mature` = true. Use on every funnel visual.
- *Complete cells*: include `is_complete` = true. Use on every retention visual.

## 3. Pages

Add a **date range control** and a **drop-down control** on `segment` at the top of the first page, then
right-click each and choose "Make report-level" so they apply everywhere. Set the default date range to
a fixed range ending 30 Sep 2026 (the data's as-of date).

**Overview**

- Scorecards: MRR (`kpi_revenue_by_segment`, `mrr_usd`, date range = last month of data), DAU
  (the *DAU (daily average)* field; a plain average of `dau` would average across segment rows),
  Stickiness, NRR (date range = last month),
  Activation rate (*Mature cohorts* filter).
- Time series: `month_start` by `mrr_usd`, breakdown `segment`, stacked area.
- Time series: `date_day` by `dau`, breakdown `segment`, stacked.

**Revenue**

- Stacked column chart: `month_start`; metrics `new_mrr_usd`, `expansion_mrr_usd`,
  `reactivation_mrr_usd`, and two calculated fields so losses stack below zero:
  `SUM(contraction_mrr_usd) * -1` and `SUM(churned_mrr_usd) * -1` (Looker Studio rejects a leading
  minus sign). In Style, tick Stacked bars and set Bars to 30; sort by `month_start` ascending.
- Time series: `month_start` by `mrr_usd` and `billed_revenue_usd`.
- Table: `segment` with NRR and GRR (`kpi_revenue_retention`, filter `month_start` = `20260901`;
  Looker Studio date filters take `YYYYMMDD`). Heatmap number type for both columns.

**Engagement and growth**

- Pivot table with heatmap: rows `signup_week` (date granularity Year Month), columns `week_number`,
  metric Retention, *Complete cells* filter; filter `week_number` to 0, 1, 2, 4, 8, 12, 26.
- Bar chart: `onboarding_flow` by Activation rate (*Mature cohorts* filter).
- Time series: `signup_week` (granularity Year Month) by Activation rate.

Use the colours from the [dashboard spec](README.md#design-rules): in each chart's Style tab, set
SMB `#8a8f98`, Mid-Market `#2f6fdb`, Enterprise `#0b8a5f`.

## 4. Share it

Share, Manage access, **Anyone with the link can view**. Put the link at the top of the main README.

If you used the BigQuery sandbox, viewers see data using your credentials (the default "owner's
credentials" setting), so they don't need access to the project. Sandbox tables expire after 60 days;
re-run the pipeline before then, or the report will go blank.
