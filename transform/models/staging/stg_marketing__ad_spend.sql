-- Parse the export's US dates and formatted numbers. Each monthly file repeats the previous month's
-- last day, so keep one row per day, platform and campaign, from the latest file.
with parsed as (
    select
        {{ parse_us_date('date') }} as spend_date,
        platform,
        campaign as campaign_name,
        cast(impressions as {{ dbt.type_int() }}) as impressions,
        cast(clicks as {{ dbt.type_int() }}) as clicks,
        cast(replace(spend, ',', '') as {{ dbt.type_float() }}) as spend,
        currency,
        _source_file
    from {{ source('raw', 'ad_spend') }}
)

select
    d.*,
    c.channel
from ({{ dedupe('parsed', 'spend_date, platform, campaign_name', '_source_file desc') }}) as d
left join {{ ref('ad_platform_channels') }} as c
    on d.platform = c.platform
