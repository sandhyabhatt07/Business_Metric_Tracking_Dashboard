# Metrics spec

The single, governed definition of every KPI on the leadership dashboard. If a number on a slide
disagrees with this document, the slide is wrong. Changes go through a pull request reviewed by the
metric owner.

## Why this exists

Before this project, three teams reported three different numbers for the same question:

| Question | Product said | Sales said | Finance said |
|---|---|---|---|
| How many active users? | Raw event count from the app, including QA staff and duplicated mobile events | Accounts with a login this month | Paid seats on invoices |
| What is revenue? | n/a | Contract value in the CRM, by rep-entered segment | Cash collected, in mixed currencies |
| Which segment is a customer in? | n/a | Whatever the rep typed (`smb`, `Small Business`, `MM`...) | Plan name as a proxy |

Every definition below fixes one of those disagreements.

## Shared rules

These apply to every metric unless it says otherwise.

- **Time zone.** All dates are UTC calendar dates.
- **Internal users are excluded.** Any user whose email ends in `@pulseboard.io`, and the `PulseBoard QA`
  workspace (account 1000).
- **Anonymous events are excluded.** Events with no `user_id`.
- **Clock-skewed events are excluded.** Events whose `event_ts` is more than 1 day after `received_at`.
- **Events are deduplicated** on `event_id`, keeping the first `received_at`.
- **Segment comes from the CRM**, normalised to `SMB`, `Mid-Market` or `Enterprise`. When a company has
  several CRM records, the most recently modified one wins. Accounts missing from the CRM get `Unknown`.
- **Currency.** Money is reported in USD, converted at the USD rate for the relevant date. Weekend and
  holiday rates use the most recent prior business day.
- **Incomplete periods are flagged, not hidden.** The current week or month is labelled as partial on
  the dashboard.

## 1. Daily Active Users (DAU)

| | |
|---|---|
| **Definition** | Distinct users with at least one qualifying event on a UTC date. |
| **Qualifying events** | Any event a person triggers in the product: `session_start`, `view_dashboard`, `run_query`, `create_report`, `share_report`, `export_data`, plus funnel events (`signup`, `onboarding_completed`, `report_created`, `trial_started`, `invite_sent`, `invite_accepted`). |
| **Grain** | One row per date (and per segment, platform). |
| **Source** | App DB `events` + `users`, CRM for segment. |
| **Companion metrics** | WAU and MAU (distinct users over the trailing 7 and 28 days, ending on the date), and stickiness = DAU / MAU. |
| **Owner** | Product Analytics |

**Why distinct users and not event counts.** In January 2026 an iOS bug fired `session_start` twice per
session for three days. Event counts jumped about 2x on iOS; DAU did not move. Counting people, not
rows, makes the metric robust to logging bugs.

**Watch out for.** The 14 July 2025 outage shows as a real DAU dip. It is kept in the data and annotated
on the dashboard, not smoothed away.

## 2. Revenue by segment

Two revenue metrics, used for different questions. Leadership's headline is **MRR**.

### 2a. Monthly Recurring Revenue (MRR)

| | |
|---|---|
| **Definition** | For every subscription active at the end of the month: `seats x unit_price x (1 - discount)`, as a monthly amount, converted to USD at the month-end rate. Annual plans count 1/12 of their yearly value each month. |
| **Active** | `started_at <= month_end` and (`ended_at` is null or `ended_at > month_end`). |
| **Grain** | One row per month per account; rolled up by segment, plan, region. |
| **Source** | App DB `subscriptions`, FX feed, CRM for segment. |
| **Owner** | Finance |

**MRR movements** explain the change month over month. Movements are classified in the account's
own currency, so a weaker euro doesn't look like customers downgrading. Every account-month falls in
exactly one bucket:

- **New**: first month with MRR.
- **Expansion**: MRR went up (more seats or a plan upgrade).
- **Contraction**: MRR went down but is still above zero.
- **Churned**: had MRR last month, none this month.
- **Reactivation**: no MRR last month, had MRR at some earlier point.
- **Retained**: unchanged in local currency.

Expansion and contraction are valued at this month's exchange rate. Whatever is left of the USD change
for continuing accounts is reported as **FX impact**, so that:

`MRR(end) = MRR(start) + New + Expansion + Reactivation - Contraction - Churned + FX impact`

The dbt test `assert_mrr_movements_reconcile` enforces this identity every run, and a dbt unit test pins
down the classification rules.

### 2b. Billed revenue

| | |
|---|---|
| **Definition** | Sum of invoices with status `paid`, by invoice issue date, converted to USD at the issue-date rate. `refunded` invoices (paid, then returned) and `failed` invoices are excluded; a retried payment produces its own `paid` invoice. |
| **Grain** | One row per invoice. |
| **Source** | App DB `invoices`, FX feed. |
| **Owner** | Finance |

**MRR and billed revenue will not match, and that's expected.** An annual plan bills 12 months up front
but adds only 1/12 to MRR. Use MRR for growth and health, and billed revenue for cash.

## 3. Funnel conversion

The self-serve funnel, measured per **signup cohort** (accounts grouped by the date they signed up).

| Step | Event | Conversion window |
|---|---|---|
| 1. Signed up | `signup` (workspace owner) | |
| 2. Onboarded | `onboarding_completed` | within 1 day of signup |
| 3. Activated | first `report_created` | within 7 days of signup |
| 4. Started trial | `trial_started` | within 30 days of signup |
| 5. Paid | first subscription `started_at` | within 45 days of signup |

| | |
|---|---|
| **Step conversion** | Accounts reaching step N / accounts reaching step N-1, within the windows above. Steps are strict: an account that starts a trial without activating first doesn't count as reaching the trial step. |
| **Overall conversion** | Accounts reaching Paid / accounts that signed up. |
| **Grain** | One row per account, with a timestamp per step; aggregated by signup week, channel, segment and onboarding flow. |
| **Source** | App DB `events`, `subscriptions`, `accounts`. |
| **Owner** | Growth |

**Cohorts need time to mature.** A cohort is only reported once its longest window (45 days) has passed.
Younger cohorts are shown greyed out as "maturing".

**Activation** (step 3) is the north-star input metric. It is also the primary metric of the
`onboarding_checklist_v1` A/B test (Feb to Apr 2026), analysed in the experiment notebook.

## 4. Retention

### 4a. User retention (product)

| | |
|---|---|
| **Definition** | For users who signed up in week W, the share who were active (any qualifying DAU event) during week W+N, where weeks are counted from each user's own signup date. |
| **Reported at** | Week 1, 4, 8, 12 and 26. |
| **Grain** | One row per signup cohort per week number. |
| **Source** | App DB `events`, `users`. |
| **Owner** | Product Analytics |

A cohort's week-N cell is only shown once all its users are at least N weeks old.

### 4b. Revenue retention (customers)

| | |
|---|---|
| **Logo retention** | Of accounts paying 12 months ago, the share still paying today. |
| **Gross revenue retention (GRR)** | For accounts paying 12 months ago: `sum(min(MRR today, MRR then)) / sum(MRR then)`. Counts contraction and churn but not expansion, so it is at most 100%. |
| **Net revenue retention (NRR)** | `MRR today from accounts that were paying 12 months ago / their MRR 12 months ago`. Includes expansion; can exceed 100%. |
| **Currency** | Both months are valued at today's exchange rates (constant currency). |
| **Grain** | Monthly, by segment. |
| **Source** | MRR model (2a). |
| **Owner** | Finance |

## Glossary

- **Account**: a customer workspace. One per company signup. This is the unit sales and finance care about.
- **User**: a person with a login. Accounts have one owner and any number of invited members.
- **Segment**: company size from the CRM. SMB has under 100 employees, Mid-Market has 100 to 999, and
  Enterprise has 1,000 or more.
- **Signup channel**: how the account found us (`organic`, `paid_search`, `paid_social`, `referral`,
  `partner`, `outbound_sales`). Ad-platform names map to channels: Google Ads to `paid_search`, Meta Ads
  and LinkedIn Ads to `paid_social`.
