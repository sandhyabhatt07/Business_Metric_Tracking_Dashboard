"""Export the dashboard tables to CSV, for Power BI or Looker Studio without a BigQuery connection.

    python -m analysis.export_marts            # writes data/exports/*.csv
"""

from pathlib import Path

from .warehouse import ROOT, table

TABLES = [
    "metrics.kpi_daily_active_users",
    "metrics.kpi_revenue_by_segment",
    "metrics.kpi_revenue_retention",
    "metrics.kpi_funnel_by_cohort",
    "metrics.kpi_user_retention_cohorts",
    "metrics.kpi_acquisition_monthly",
    "metrics.kpi_onboarding_experiment",
    "ml.churn_risk_scores",
]


def main(out: Path = ROOT / "data" / "exports") -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name in TABLES:
        df = table(name)
        df.to_csv(out / f"{name.split('.')[1]}.csv", index=False)
        print(f"{name:<40} {len(df):>8,} rows")


if __name__ == "__main__":
    main()
