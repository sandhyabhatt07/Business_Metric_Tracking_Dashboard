# Build the dashboard in Power BI

About an hour the first time. You need Power BI Desktop (free, Windows) and either the BigQuery project
from [docs/setup.md](../docs/setup.md) or the CSV exports.

## 1. Get the data

**From BigQuery (recommended).** Home, Get data, **Google BigQuery**, sign in with the Google account
that owns the project. Under your project, select:

- `metrics`: all seven `kpi_*` tables
- `ml`: `churn_risk_scores` (only after you've run `notebooks/03_churn_model.ipynb` against BigQuery)

Choose **Import** (the tables are small).

**From CSV.** Run `python -m analysis.export_marts`, then Get data, Text/CSV, and load each file in
`data/exports/`. Keep the file names as table names (for example `kpi_revenue_by_segment`).

In Power Query, check the types: `date_day`, `month_start`, `signup_week` and `scored_at` are **Date**;
`is_mature` and `is_complete` are **True/False**; counts are **Whole number**; everything ending in
`_usd`, `_rate` or `_probability` is **Decimal number**.

## 2. Model

1. Create the calculated tables `Date`, `Segment` and `Funnel Steps` from [measures.dax](measures.dax).
   Mark `Date` as a date table. Sort `Segment[Segment]` by `Sort Order` and `Funnel Steps[Step]` by
   `Step Order`.
2. Create these relationships (Model view): all many-to-one, single direction, from the KPI table to
   the dimension.

| From | To |
|---|---|
| `kpi_daily_active_users[date_day]` | `Date[Date]` |
| `kpi_revenue_by_segment[month_start]` | `Date[Date]` |
| `kpi_revenue_retention[month_start]` | `Date[Date]` |
| `kpi_funnel_by_cohort[signup_week]` | `Date[Date]` |
| `kpi_user_retention_cohorts[signup_week]` | `Date[Date]` |
| `kpi_acquisition_monthly[month_start]` | `Date[Date]` |
| `kpi_daily_active_users[segment]` | `Segment[Segment]` |
| `kpi_revenue_by_segment[segment]` | `Segment[Segment]` |
| `kpi_revenue_retention[segment]` | `Segment[Segment]` |
| `kpi_funnel_by_cohort[segment]` | `Segment[Segment]` |
| `kpi_user_retention_cohorts[segment]` | `Segment[Segment]` |
| `churn_risk_scores[segment]` | `Segment[Segment]` |

This is a star: shared `Date` and `Segment` dimensions, so one pair of slicers filters every page.
`kpi_acquisition_monthly` is by channel, not segment, so the segment slicer doesn't affect it; say so
in that visual's title.

3. Create a table called `_Measures` (Enter data, one empty column), then paste every measure from
   [measures.dax](measures.dax) into it. Set formats: currency for MRR, ARR, ARPA and spend;
   percentage for rates, retention, stickiness and MoM %.
4. View, Themes, Browse for themes: [pulseboard_theme.json](pulseboard_theme.json).

## 3. Pages

Follow the layouts in the [dashboard spec](README.md#pages). Put the same two slicers at the top of
every page: `Date[Month]` (between) and `Segment[Segment]` (dropdown), and use View, Sync slicers so
they carry across pages. Add a card with `Data As Of` in the header.

| Page | Visual | Fields |
|---|---|---|
| Overview | 6 cards | `MRR`, `MRR MoM %`, `DAU`, `Stickiness`, `NRR`, `Activation Rate` |
| | Stacked area | Axis `Date[Month]`, values `MRR`, legend `Segment[Segment]` |
| | Line | Axis `Date[Date]`, values `DAU` (add a 7-day moving average with Analytics, Trend) |
| | Clustered column | Axis `Date[Month]`, values `Net New MRR` |
| | Funnel | Category `Funnel Steps[Step]`, values `Funnel Accounts` |
| Revenue | Stacked column + line | Axis `Date[Month]`; columns `New MRR`, `Expansion MRR`, `Reactivation MRR`, `Contraction MRR`, `Churned MRR`; line `Net New MRR` |
| | Line | Axis `Date[Month]`, values `MRR`, `Billed Revenue` |
| | Clustered bar | Axis `Segment[Segment]`, values `NRR`, `GRR`, `Logo Retention` |
| | Table | `Segment[Segment]`, `MRR`, `Paying Accounts`, `ARPA`, `NRR` |
| Engagement | Line | Axis `Date[Date]`, values `DAU`, `WAU`, `MAU` |
| | Matrix | Rows `Date[Month]`, columns `kpi_user_retention_cohorts[week_number]` (filter to 0, 1, 2, 4, 8, 12, 26), values `Retention %`, conditional formatting: background colour scale |
| | Clustered column | Axis `Segment[Segment]`, values `Week 1 Retention`, `Week 4 Retention`, `Week 12 Retention` |
| Growth | Line | Axis `Date[Month]`, values `Activation Rate` (add a constant line or shaded text box for the 2 Feb to 26 Apr 2026 test) |
| | Clustered column | Axis `kpi_onboarding_experiment[variant]`, values `Experiment Activation Rate` |
| | Card | `Experiment Lift (pts)` |
| | Line and column | Axis `Date[Month]`, legend `kpi_acquisition_monthly[channel]`, columns `Ad Spend`, line `CAC` |
| Customer risk | 3 cards | `Expected MRR at Risk`, `High-Risk Accounts`, `High-Risk MRR` |
| | Table | `churn_risk_scores` columns `account_id`, `segment`, `mrr_usd`, `churn_probability`, `user_days_trend`, `days_since_last_active`, `months_to_renewal`, `expected_mrr_at_risk_usd`; filter `risk_tier` = High; sort by expected MRR at risk |

## 4. Check the numbers

Before you publish screenshots, check a few values against the warehouse. With the default data
(seed 42), September 2026 should show:

| Measure | Expected |
|---|---|
| MRR | about $223k |
| Paying accounts | 847 |
| DAU (September average) | about 1,090 |
| Activation rate, A/B test | control 41%, treatment 51% |

If a number is off, the usual cause is a missing relationship or a date column loaded as text.

## 5. Share it

Power BI Desktop can't publish publicly without a work account, so for the portfolio:

1. Save the report as `dashboard/PulseBoard.pbix` (it's under 10 MB with this data; commit it).
2. Export each page as a PNG (File, Export, Export to PDF, or a screenshot) into `dashboard/screenshots/`.
3. Link the screenshots from the main README.
