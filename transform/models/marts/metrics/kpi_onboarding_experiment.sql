-- Funnel outcomes for the onboarding_checklist_v1 A/B test, per variant. The statistics live in
-- notebooks/; this table is what the dashboard shows.
select
    a.onboarding_experiment_variant as variant,
    count(*) as accounts,
    sum(case when f.is_onboarded then 1 else 0 end) as onboarded,
    sum(case when f.is_activated then 1 else 0 end) as activated,
    sum(case when f.is_trial_started then 1 else 0 end) as trial_started,
    sum(case when f.is_paid then 1 else 0 end) as paid,
    sum(case when f.is_activated then 1 else 0 end) / count(*) as activation_rate
from {{ ref('dim_account') }} as a
inner join {{ ref('int_account_funnel') }} as f on a.account_id = f.account_id
where a.onboarding_experiment_variant is not null
group by 1
