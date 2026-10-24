select
    cast(rate_date as date) as rate_date,
    base_currency,
    currency,
    cast(rate as {{ dbt.type_float() }}) as usd_rate
from {{ source('raw', 'fx_rates') }}
