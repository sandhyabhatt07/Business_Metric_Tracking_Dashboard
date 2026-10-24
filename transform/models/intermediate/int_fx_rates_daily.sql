-- A USD rate for every calendar day and currency. Weekends and holidays reuse the last published rate.
with spine as (
    {{ calendar_days(var('history_start'), var('spine_end')) }}
),

rates as (
    select rate_date, currency, usd_rate from {{ ref('stg_fx__rates') }}
    union all
    select cast(date_day as date), 'USD', 1.0 from spine
),

grid as (
    select cast(s.date_day as date) as rate_date, c.currency
    from spine as s
    cross join (select distinct currency from rates) as c
)

select
    g.rate_date,
    g.currency,
    last_value(r.usd_rate ignore nulls) over (
        partition by g.currency order by g.rate_date rows between unbounded preceding and current row
    ) as usd_rate,
    r.usd_rate is not null as is_published
from grid as g
left join rates as r
    on g.rate_date = r.rate_date and g.currency = r.currency
