select
    invoice_id,
    account_id,
    subscription_id,
    status,
    amount_minor / 100.0 as amount_local,
    currency,
    period_start,
    period_end,
    issued_at,
    cast(issued_at as date) as issued_date
from {{ source('raw', 'app_invoices') }}
