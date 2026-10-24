-- DAU, WAU and MAU by segment. A user belongs to one account and so one segment, which makes every
-- column additive across segments: sum them for the company total.
with activity as (
    select a.user_id, a.activity_date, d.segment
    from {{ ref('fct_user_daily_activity') }} as a
    inner join {{ ref('dim_account') }} as d on a.account_id = d.account_id
),

days as (
    select date_day from {{ ref('dim_date') }}
    where date_day between {{ history_start() }} and {{ as_of_date() }}
),

segments as (
    select distinct segment from activity
),

rolling as (
    select
        d.date_day,
        a.segment,
        count(distinct case when a.activity_date = d.date_day then a.user_id end) as dau,
        count(distinct case when a.activity_date >= {{ add_days('d.date_day', -6) }} then a.user_id end) as wau,
        count(distinct a.user_id) as mau
    from days as d
    inner join activity as a
        on a.activity_date between {{ add_days('d.date_day', -27) }} and d.date_day
    group by 1, 2
)

select
    d.date_day,
    s.segment,
    coalesce(r.dau, 0) as dau,
    coalesce(r.wau, 0) as wau,
    coalesce(r.mau, 0) as mau
from days as d
cross join segments as s
left join rolling as r on d.date_day = r.date_day and s.segment = r.segment
