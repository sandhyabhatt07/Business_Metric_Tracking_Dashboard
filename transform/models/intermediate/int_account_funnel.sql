-- One row per customer account with the time it reached each funnel step. Steps are strict: an account
-- only reaches a step if it reached the previous one, inside the windows in docs/metrics_spec.md.
with accounts as (
    select account_id, created_at as signed_up_at, signup_date
    from {{ ref('stg_app__accounts') }}
    where not is_internal
),

milestones as (
    select
        u.account_id,
        min(case when e.event_name = 'onboarding_completed' then e.event_ts end) as onboarded_at,
        min(case when e.event_name = 'report_created' then e.event_ts end) as activated_at,
        min(case when e.event_name = 'trial_started' then e.event_ts end) as trial_started_at
    from {{ ref('stg_app__events') }} as e
    inner join {{ ref('stg_app__users') }} as u on e.user_id = u.user_id
    where e.event_name in ('onboarding_completed', 'report_created', 'trial_started')
        and not e.is_clock_skewed
    group by 1
),

first_paid as (
    select account_id, min(started_at) as paid_at
    from {{ ref('stg_app__subscriptions') }}
    group by 1
),

timed as (
    select
        a.account_id,
        a.signup_date,
        a.signed_up_at,
        m.onboarded_at,
        m.activated_at,
        m.trial_started_at,
        p.paid_at,
        {{ within_days('a.signed_up_at', 'm.onboarded_at', 1) }} as onboarded_in_window,
        {{ within_days('a.signed_up_at', 'm.activated_at', 7) }} as activated_in_window,
        {{ within_days('a.signed_up_at', 'm.trial_started_at', 30) }} as trial_in_window,
        {{ within_days('a.signed_up_at', 'p.paid_at', 45) }} as paid_in_window
    from accounts as a
    left join milestones as m on a.account_id = m.account_id
    left join first_paid as p on a.account_id = p.account_id
)

select
    account_id,
    signup_date,
    signed_up_at,
    onboarded_at,
    activated_at,
    trial_started_at,
    paid_at,
    onboarded_in_window as is_onboarded,
    onboarded_in_window and activated_in_window as is_activated,
    onboarded_in_window and activated_in_window and trial_in_window as is_trial_started,
    onboarded_in_window and activated_in_window and trial_in_window and paid_in_window as is_paid,
    -- Cohorts are only final once the longest window (45 days) has passed.
    {{ dbt.datediff('signup_date', as_of_date(), 'day') }} >= 45 as is_mature
from timed
