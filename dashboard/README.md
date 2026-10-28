# Leadership metrics dashboard

**[Open the live dashboard (Looker Studio)](https://lookerstudio.google.com/reporting/42cee920-d8f4-443e-b7e3-b1d6b169e090)**

The dashboard reads only the governed `metrics` tables in BigQuery. It holds no business logic of its
own, so every number matches the [metrics spec](../docs/metrics_spec.md), the dbt tests and the
notebooks. The same design is built in Looker Studio (public link) and Power BI.

| File | What it is |
|---|---|
| [measures.dax](measures.dax) | Power BI model: date, segment and funnel tables, and every DAX measure |
| [pulseboard_theme.json](pulseboard_theme.json) | Power BI theme with the shared segment colours |

## Pages

**Executive overview.** MRR, paying accounts and DAU for the latest month; MRR by segment over time;
weekly active users by segment.

**Revenue.** A monthly MRR bridge (new, expansion and reactivation above zero; contraction and churn
below) and 12-month net and gross revenue retention by segment, in constant currency.

**Engagement.** A cohort retention heatmap: signup month by weeks since signup, showing only cells that
have fully happened.

## Design decisions

- **One definition per number.** Rates are computed from summed numerators and denominators
  (`SUM(active_users) / SUM(cohort_users)`), never by averaging pre-computed rates, so totals and
  segment slices always agree.
- **Averages that respect the grain.** The KPI tables have one row per day per segment, so DAU is
  `SUM(dau) / COUNT_DISTINCT(date_day)`; a plain average would understate it fourfold.
- **No half-finished cohorts.** Funnel rates use only cohorts old enough to have completed every step,
  and retention cells that haven't happened yet are left blank instead of showing as low retention.
- **Losses read as losses.** Contraction and churn plot below zero, so the chart shows what grew and
  what shrank MRR, not just the net.
- **Consistent colours.** SMB `#8a8f98`, Mid-Market `#2f6fdb`, Enterprise `#0b8a5f` on every page and
  in the notebooks.
- **Honest freshness.** The data runs to 30 Sep 2026; the header says so.
