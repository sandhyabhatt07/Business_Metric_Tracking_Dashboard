-- 12-month logo, gross and net revenue retention by segment, in constant currency (this month's rates).
-- Numerators and denominators are kept so totals can be recomputed across segments.
with m as (
    select account_id, month_start, mrr_local, usd_rate
    from {{ ref('fct_mrr_monthly') }}
),

paired as (
    select
        cur.month_start,
        a.segment,
        base.mrr_local / cur.usd_rate as base_mrr_usd,
        cur.mrr_local / cur.usd_rate as current_mrr_usd
    from m as base
    inner join m as cur
        on cur.account_id = base.account_id
        and cur.month_start = {{ add_months('base.month_start', 12) }}
    inner join {{ ref('dim_account') }} as a on base.account_id = a.account_id
    where base.mrr_local > 0
)

select
    month_start,
    segment,
    count(*) as accounts_12m_ago,
    sum(case when current_mrr_usd > 0 then 1 else 0 end) as accounts_retained,
    sum(base_mrr_usd) as mrr_12m_ago_usd,
    sum(least(current_mrr_usd, base_mrr_usd)) as gross_retained_mrr_usd,
    sum(current_mrr_usd) as net_retained_mrr_usd,
    sum(case when current_mrr_usd > 0 then 1 else 0 end) / count(*) as logo_retention,
    sum(least(current_mrr_usd, base_mrr_usd)) / sum(base_mrr_usd) as gross_revenue_retention,
    sum(current_mrr_usd) / sum(base_mrr_usd) as net_revenue_retention
from paired
group by 1, 2
