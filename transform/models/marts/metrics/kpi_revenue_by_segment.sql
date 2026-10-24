-- Monthly MRR, its movements and billed revenue by segment, in USD. Every column is additive.
with mrr as (
    select
        m.month_start,
        a.segment,
        sum(m.mrr_usd) as mrr_usd,
        sum(case when m.mrr_usd > 0 then 1 else 0 end) as paying_accounts,
        sum(m.new_mrr_usd) as new_mrr_usd,
        sum(m.expansion_mrr_usd) as expansion_mrr_usd,
        sum(m.reactivation_mrr_usd) as reactivation_mrr_usd,
        sum(m.contraction_mrr_usd) as contraction_mrr_usd,
        sum(m.churned_mrr_usd) as churned_mrr_usd,
        sum(m.fx_impact_usd) as fx_impact_usd,
        sum(case when m.movement = 'new' then 1 else 0 end) as new_accounts,
        sum(case when m.movement = 'churned' then 1 else 0 end) as churned_accounts
    from {{ ref('fct_mrr_monthly') }} as m
    inner join {{ ref('dim_account') }} as a on m.account_id = a.account_id
    group by 1, 2
),

billed as (
    select i.issued_month as month_start, a.segment, sum(i.revenue_usd) as billed_revenue_usd
    from {{ ref('fct_invoices') }} as i
    inner join {{ ref('dim_account') }} as a on i.account_id = a.account_id
    where i.issued_date <= {{ as_of_date() }}
    group by 1, 2
)

select
    coalesce(m.month_start, b.month_start) as month_start,
    coalesce(m.segment, b.segment) as segment,
    coalesce(m.mrr_usd, 0) as mrr_usd,
    coalesce(m.paying_accounts, 0) as paying_accounts,
    coalesce(m.new_mrr_usd, 0) as new_mrr_usd,
    coalesce(m.expansion_mrr_usd, 0) as expansion_mrr_usd,
    coalesce(m.reactivation_mrr_usd, 0) as reactivation_mrr_usd,
    coalesce(m.contraction_mrr_usd, 0) as contraction_mrr_usd,
    coalesce(m.churned_mrr_usd, 0) as churned_mrr_usd,
    coalesce(m.fx_impact_usd, 0) as fx_impact_usd,
    coalesce(m.new_accounts, 0) as new_accounts,
    coalesce(m.churned_accounts, 0) as churned_accounts,
    coalesce(b.billed_revenue_usd, 0) as billed_revenue_usd
from mrr as m
full outer join billed as b on m.month_start = b.month_start and m.segment = b.segment
