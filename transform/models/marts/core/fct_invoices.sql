select
    i.invoice_id,
    i.account_id,
    i.subscription_id,
    i.issued_at,
    i.issued_date,
    {{ month_start('i.issued_date') }} as issued_month,
    i.status,
    i.currency,
    i.amount_local,
    fx.usd_rate,
    i.amount_local / fx.usd_rate as amount_usd,
    -- Billed revenue counts paid invoices only; refunded and failed attempts are excluded.
    case when i.status = 'paid' then i.amount_local / fx.usd_rate else 0 end as revenue_usd
from {{ ref('stg_app__invoices') }} as i
inner join {{ ref('int_fx_rates_daily') }} as fx
    on fx.currency = i.currency and fx.rate_date = i.issued_date
