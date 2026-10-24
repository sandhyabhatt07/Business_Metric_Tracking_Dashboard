with spine as (
    {{ calendar_days(var('history_start'), var('spine_end')) }}
),

days as (
    select cast(date_day as date) as date_day from spine
)

select
    date_day,
    {{ week_start('date_day') }} as week_start,
    {{ month_start('date_day') }} as month_start,
    cast({{ dbt.last_day('date_day', 'month') }} as date) as month_end,
    extract(year from date_day) as year,
    extract(month from date_day) as month,
    cast({{ dbt.date_trunc('quarter', 'date_day') }} as date) as quarter_start,
    {{ iso_day_of_week('date_day') }} as iso_day_of_week,
    {{ iso_day_of_week('date_day') }} >= 6 as is_weekend,
    date_day <= {{ as_of_date() }} as is_reported
from days
