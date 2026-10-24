# Analysis notebooks

Each notebook reads the warehouse's governed tables, so its numbers match the dashboard. They run
against the local DuckDB warehouse by default, or BigQuery with `WAREHOUSE=bigquery`.

| Notebook | Question | Methods | Headline |
|---|---|---|---|
| [01_onboarding_ab_test](01_onboarding_ab_test.ipynb) | Did the guided onboarding checklist work? | Sample ratio check, two-proportion z-tests, Newcombe intervals, power analysis, segment consistency, post-rollout check | Activation up about 10 points (41% to 51%, p < 0.001); no measurable revenue effect, and the test was too small to see one |
| [02_retention](02_retention.ipynb) | Do users and customers stay? | Cohort retention matrix, Kaplan-Meier survival with censoring, logo/gross/net revenue retention | Week 1 decides most outcomes; activated owners retain far better than others; Enterprise NRR above 100%, SMB well below |
| [03_churn_model](03_churn_model.ipynb) | Which paying accounts will cancel in the next 60 days? | Point-in-time snapshots, time-based split, logistic regression vs gradient boosting, PR curves, lift, calibration, permutation importance | ROC AUC 0.80; the top 10% riskiest accounts hold about 40% of churners (4x lift); scores written to `ml.churn_risk_scores` |

Run them:

```bash
pip install -r ../requirements-analysis.txt
make -C .. notebooks
```
