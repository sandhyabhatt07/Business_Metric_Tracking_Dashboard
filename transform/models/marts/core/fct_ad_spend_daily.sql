select
    s.spend_date,
    s.platform,
    s.channel,
    s.campaign_name,
    s.impressions,
    s.clicks,
    s.spend / fx.usd_rate as spend_usd
from {{ ref('stg_marketing__ad_spend') }} as s
inner join {{ ref('int_fx_rates_daily') }} as fx
    on fx.currency = s.currency and fx.rate_date = s.spend_date
