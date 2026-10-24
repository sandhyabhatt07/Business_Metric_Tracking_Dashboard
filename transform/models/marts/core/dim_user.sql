select
    u.user_id,
    u.account_id,
    u.role,
    u.signup_channel,
    u.primary_platform,
    u.onboarding_flow,
    u.created_at,
    u.signup_date,
    {{ week_start('u.signup_date') }} as signup_week,
    u.is_internal,
    a.segment
from {{ ref('stg_app__users') }} as u
left join {{ ref('dim_account') }} as a on u.account_id = a.account_id
