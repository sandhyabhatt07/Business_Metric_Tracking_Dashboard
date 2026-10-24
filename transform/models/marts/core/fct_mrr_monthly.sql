-- MRR per account per month in USD, with the movement that explains the change since last month.
-- Movements are classified in local currency, so exchange-rate swings land in fx_impact_usd instead of
-- looking like expansion or contraction. For every account-month:
--   mrr_usd = previous_mrr_usd + new + expansion + reactivation - contraction - churned + fx_impact
with m as (
    select
        *,
        lag(mrr_local) over (partition by account_id order by month_start) as prev_mrr_local,
        lag(usd_rate) over (partition by account_id order by month_start) as prev_usd_rate,
        max(case when mrr_local > 0 then 1 else 0 end) over (
            partition by account_id order by month_start rows between unbounded preceding and 1 preceding
        ) as paid_before
    from {{ ref('int_mrr_account_months') }}
),

classified as (
    select
        account_id,
        month_start,
        currency,
        mrr_local,
        usd_rate,
        mrr_local / usd_rate as mrr_usd,
        coalesce(prev_mrr_local / prev_usd_rate, 0) as previous_mrr_usd,
        -- Last month's MRR at this month's rate: the base for constant-currency comparisons.
        coalesce(prev_mrr_local, 0) / usd_rate as previous_mrr_usd_constant_fx,
        case
            when mrr_local > 0 and coalesce(prev_mrr_local, 0) = 0 and coalesce(paid_before, 0) = 0 then 'new'
            when mrr_local > 0 and coalesce(prev_mrr_local, 0) = 0 then 'reactivation'
            when mrr_local = 0 and coalesce(prev_mrr_local, 0) > 0 then 'churned'
            when mrr_local > prev_mrr_local then 'expansion'
            when mrr_local < prev_mrr_local then 'contraction'
            when mrr_local > 0 then 'retained'
            else 'inactive'
        end as movement
    from m
)

select
    account_id,
    month_start,
    currency,
    mrr_local,
    usd_rate,
    mrr_usd,
    previous_mrr_usd,
    movement,
    case when movement = 'new' then mrr_usd else 0 end as new_mrr_usd,
    case when movement = 'reactivation' then mrr_usd else 0 end as reactivation_mrr_usd,
    case when movement = 'expansion' then mrr_usd - previous_mrr_usd_constant_fx else 0 end as expansion_mrr_usd,
    case when movement = 'contraction' then previous_mrr_usd_constant_fx - mrr_usd else 0 end
        as contraction_mrr_usd,
    case when movement = 'churned' then previous_mrr_usd else 0 end as churned_mrr_usd,
    case when movement in ('expansion', 'contraction', 'retained')
        then previous_mrr_usd_constant_fx - previous_mrr_usd else 0 end as fx_impact_usd
from classified
