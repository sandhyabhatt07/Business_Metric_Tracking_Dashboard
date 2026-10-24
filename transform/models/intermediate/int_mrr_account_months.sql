-- MRR per paying account per month, from its first paid month to the as-of month (0 once churned).
with months as (
    select distinct month_start, month_end
    from {{ ref('dim_date') }}
    where month_start <= {{ as_of_date() }}
),

subs as (
    select account_id, currency, start_date, end_date, mrr_local
    from {{ ref('stg_app__subscriptions') }}
),

active as (
    -- Active at month end: started on or before it, not ended by it.
    select m.month_start, m.month_end, s.account_id, s.currency, sum(s.mrr_local) as mrr_local
    from months as m
    inner join subs as s
        on s.start_date <= m.month_end and (s.end_date is null or s.end_date > m.month_end)
    group by 1, 2, 3, 4
),

accounts as (
    select account_id, max(currency) as currency, min(month_start) as first_month
    from active
    group by 1
),

grid as (
    select a.account_id, a.currency, m.month_start, m.month_end
    from accounts as a
    inner join months as m on m.month_start >= a.first_month
)

select
    g.account_id,
    g.month_start,
    g.month_end,
    g.currency,
    coalesce(act.mrr_local, 0) as mrr_local,
    -- Rate on the month's last day, or on the as-of date for the current month.
    fx.usd_rate
from grid as g
left join active as act
    on g.account_id = act.account_id and g.month_start = act.month_start
inner join {{ ref('int_fx_rates_daily') }} as fx
    on fx.currency = g.currency and fx.rate_date = least(g.month_end, {{ as_of_date() }})
