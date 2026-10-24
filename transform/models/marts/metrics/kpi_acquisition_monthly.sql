-- Signups, new paying customers and paid-media spend per channel per month.
with signups as (
    select
        {{ month_start('a.signup_date') }} as month_start,
        a.signup_channel as channel,
        count(*) as signups,
        sum(case when f.is_paid then 1 else 0 end) as converted_to_paid
    from {{ ref('dim_account') }} as a
    inner join {{ ref('int_account_funnel') }} as f on a.account_id = f.account_id
    where a.signup_date <= {{ as_of_date() }}
    group by 1, 2
),

spend as (
    select {{ month_start('spend_date') }} as month_start, channel, sum(spend_usd) as spend_usd
    from {{ ref('fct_ad_spend_daily') }}
    group by 1, 2
)

select
    s.month_start,
    s.channel,
    s.signups,
    s.converted_to_paid,
    coalesce(sp.spend_usd, 0) as spend_usd,
    sp.spend_usd / nullif(s.signups, 0) as cost_per_signup_usd,
    sp.spend_usd / nullif(s.converted_to_paid, 0) as cac_usd
from signups as s
left join spend as sp on s.month_start = sp.month_start and s.channel = sp.channel
