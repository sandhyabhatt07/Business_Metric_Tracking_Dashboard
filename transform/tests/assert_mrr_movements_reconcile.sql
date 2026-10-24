-- Each month's MRR must equal last month's plus every movement (docs/metrics_spec.md, section 2a).
with monthly as (
    select
        month_start,
        sum(mrr_usd) as mrr_usd,
        sum(previous_mrr_usd) as previous_mrr_usd,
        sum(new_mrr_usd + expansion_mrr_usd + reactivation_mrr_usd
            - contraction_mrr_usd - churned_mrr_usd + fx_impact_usd) as net_movement_usd
    from {{ ref('fct_mrr_monthly') }}
    group by 1
)

select *
from monthly
where abs(mrr_usd - previous_mrr_usd - net_movement_usd) > 0.01
