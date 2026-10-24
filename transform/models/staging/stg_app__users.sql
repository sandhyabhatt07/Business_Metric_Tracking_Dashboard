select
    user_id,
    account_id,
    lower(email) as email,
    role,
    signup_channel,
    onboarding_flow,
    primary_platform,
    created_at,
    cast(created_at as date) as signup_date,
    (lower(email) like '%@{{ var("internal_email_domain") }}'
        or account_id = {{ var('internal_account_id') }}) as is_internal
from {{ source('raw', 'app_users') }}
