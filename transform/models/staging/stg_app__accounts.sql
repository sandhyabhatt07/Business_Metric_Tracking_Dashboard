select
    account_id,
    workspace_name,
    owner_user_id,
    country,
    signup_channel,
    created_at,
    cast(created_at as date) as signup_date,
    account_id = {{ var('internal_account_id') }} as is_internal
from {{ source('raw', 'app_accounts') }}
