-- Signup funnel counts by signup week and the dimensions growth teams slice by. Counts are additive.
select
    {{ week_start('f.signup_date') }} as signup_week,
    a.segment,
    a.signup_channel,
    a.onboarding_flow,
    f.is_mature,
    count(*) as signups,
    sum(case when f.is_onboarded then 1 else 0 end) as onboarded,
    sum(case when f.is_activated then 1 else 0 end) as activated,
    sum(case when f.is_trial_started then 1 else 0 end) as trial_started,
    sum(case when f.is_paid then 1 else 0 end) as paid
from {{ ref('int_account_funnel') }} as f
inner join {{ ref('dim_account') }} as a on f.account_id = a.account_id
where f.signup_date <= {{ as_of_date() }}
group by 1, 2, 3, 4, 5
