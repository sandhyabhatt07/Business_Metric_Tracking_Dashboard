{# Small helpers so every model runs on both BigQuery (production) and DuckDB (local and CI). #}

{# Keep the first row per key. #}
{% macro dedupe(relation, partition_by, order_by) -%}
    {{ return(adapter.dispatch('dedupe')(relation, partition_by, order_by)) }}
{%- endmacro %}

{% macro bigquery__dedupe(relation, partition_by, order_by) -%}
    select * except (_dedupe_rn) from (
        select *, row_number() over (partition by {{ partition_by }} order by {{ order_by }}) as _dedupe_rn
        from {{ relation }}
    ) where _dedupe_rn = 1
{%- endmacro %}

{% macro default__dedupe(relation, partition_by, order_by) -%}
    select * exclude (_dedupe_rn) from (
        select *, row_number() over (partition by {{ partition_by }} order by {{ order_by }}) as _dedupe_rn
        from {{ relation }}
    ) where _dedupe_rn = 1
{%- endmacro %}

{# 'MM/DD/YYYY' text to a date. #}
{% macro parse_us_date(col) -%}
    {{ return(adapter.dispatch('parse_us_date')(col)) }}
{%- endmacro %}

{% macro bigquery__parse_us_date(col) -%}
    parse_date('%m/%d/%Y', {{ col }})
{%- endmacro %}

{% macro default__parse_us_date(col) -%}
    cast(strptime({{ col }}, '%m/%d/%Y') as date)
{%- endmacro %}

{# ISO 8601 text such as '2025-01-14T10:02:11.000Z' to a UTC timestamp. #}
{% macro parse_iso_timestamp(col) -%}
    cast(replace(replace({{ col }}, 'T', ' '), 'Z', '') as {{ dbt.type_timestamp() }})
{%- endmacro %}

{# Monday of the ISO week containing a date. #}
{% macro week_start(col) -%}
    {{ return(adapter.dispatch('week_start')(col)) }}
{%- endmacro %}

{% macro bigquery__week_start(col) -%}
    date_trunc({{ col }}, isoweek)
{%- endmacro %}

{% macro default__week_start(col) -%}
    cast(date_trunc('week', {{ col }}) as date)
{%- endmacro %}

{% macro month_start(col) -%}
    cast({{ dbt.date_trunc('month', col) }} as date)
{%- endmacro %}

{# BigQuery intervals must be INT64, and expressions such as dbt_utils' generated_number come out as FLOAT64. #}
{% macro add_days(date_col, n) -%}
    cast({{ dbt.dateadd('day', 'cast(' ~ n ~ ' as ' ~ dbt.type_int() ~ ')', date_col) }} as date)
{%- endmacro %}

{% macro add_months(date_col, n) -%}
    cast({{ dbt.dateadd('month', 'cast(' ~ n ~ ' as ' ~ dbt.type_int() ~ ')', date_col) }} as date)
{%- endmacro %}

{# True when `later_ts` happened within `days` days after `earlier_ts`. #}
{% macro within_days(earlier_ts, later_ts, days) -%}
    coalesce({{ later_ts }} >= {{ earlier_ts }}
        and {{ dbt.datediff(earlier_ts, later_ts, 'second') }} <= {{ days * 86400 }}, false)
{%- endmacro %}

{% macro as_of_date() -%}
    cast('{{ var("as_of_date") }}' as date)
{%- endmacro %}

{% macro history_start() -%}
    cast('{{ var("history_start") }}' as date)
{%- endmacro %}

{# BigQuery partitioning for big tables, except in the free sandbox, which expires partitions older than 60 days. #}
{% macro bq_partition(field) -%}
    {%- if target.type == 'bigquery' and env_var('BQ_SANDBOX', 'true') | lower not in ['1', 'true', 'yes'] -%}
        {{ return({'field': field, 'data_type': 'date'}) }}
    {%- endif -%}
    {{ return(none) }}
{%- endmacro %}

{# ISO day of week: Monday = 1 ... Sunday = 7. #}
{% macro iso_day_of_week(col) -%}
    {{ return(adapter.dispatch('iso_day_of_week')(col)) }}
{%- endmacro %}

{% macro bigquery__iso_day_of_week(col) -%}
    mod(extract(dayofweek from {{ col }}) + 5, 7) + 1
{%- endmacro %}

{% macro default__iso_day_of_week(col) -%}
    extract(isodow from {{ col }})
{%- endmacro %}

{# One row per day in [start, end). Computed at compile time, so it needs no warehouse query. #}
{% macro calendar_days(start, end) -%}
    {%- set n = (modules.datetime.date.fromisoformat(end) - modules.datetime.date.fromisoformat(start)).days -%}
    select {{ add_days("cast('" ~ start ~ "' as date)", '(generated_number - 1)') }} as date_day
    from ({{ dbt_utils.generate_series(n) }}) as series
{%- endmacro %}
