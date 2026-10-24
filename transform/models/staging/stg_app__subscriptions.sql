select
    subscription_id,
    account_id,
    plan,
    billing_interval,
    seats,
    unit_price_minor / 100.0 as unit_price,
    discount_pct,
    currency,
    status,
    cancel_reason,
    started_at,
    ended_at,
    cast(started_at as date) as start_date,
    cast(ended_at as date) as end_date,
    -- Monthly recurring amount in local currency; annual plans are priced per month too.
    seats * unit_price_minor / 100.0 * (1 - discount_pct / 100.0) as mrr_local
from {{ source('raw', 'app_subscriptions') }}
