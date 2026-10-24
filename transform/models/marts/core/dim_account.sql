-- One row per workspace. Segment, industry and sales owner come from the CRM (latest record).
with accounts as (
    select * from {{ ref('stg_app__accounts') }}
),

crm as (
    select * from {{ ref('stg_crm__companies') }}
),

owners as (
    select user_id, onboarding_flow from {{ ref('stg_app__users') }}
),

experiment as (
    select user_id, variant
    from {{ ref('stg_app__experiment_assignments') }}
    where experiment_name = 'onboarding_checklist_v1'
),

subs as (
    select
        account_id,
        min(started_at) as first_paid_at,
        max(case when ended_at is null then plan end) as current_plan,
        sum(case when ended_at is null then mrr_local else 0 end) as current_mrr_local,
        max(case when status = 'canceled' then ended_at end) as canceled_at,
        max(case when status = 'canceled' then cancel_reason end) as cancel_reason
    from {{ ref('stg_app__subscriptions') }}
    group by 1
)

select
    a.account_id,
    a.workspace_name,
    a.is_internal,
    a.created_at,
    a.signup_date,
    a.signup_channel,
    a.country,
    crm.region,
    case when a.is_internal then 'Internal' else coalesce(crm.segment, 'Unknown') end as segment,
    coalesce(crm.industry, 'Unknown') as industry,
    crm.employee_count,
    crm.crm_owner,
    crm.crm_company_id is not null as is_in_crm,
    o.onboarding_flow,
    x.variant as onboarding_experiment_variant,
    s.first_paid_at,
    s.current_plan,
    s.current_mrr_local,
    s.canceled_at,
    s.cancel_reason,
    case
        when s.current_plan is not null then 'paying'
        when s.first_paid_at is not null then 'churned'
        else 'free'
    end as customer_status
from accounts as a
left join crm on a.account_id = crm.account_id
left join owners as o on a.owner_user_id = o.user_id
left join experiment as x on a.owner_user_id = x.user_id
left join subs as s on a.account_id = s.account_id
