{{ config(materialized='table', partition_by=bq_partition('event_date'),
          cluster_by=['event_name', 'user_id'] if target.type == 'bigquery' else none) }}

-- One row per event_id: the raw log repeats events from retried uploads and overlapping loads.
with deduped as (
    {{ dedupe(source('raw', 'app_events'), 'event_id', 'received_at, _loaded_at') }}
)

select
    event_id,
    user_id,
    session_id,
    event_name,
    event_ts,
    cast(event_ts as date) as event_date,
    received_at,
    platform,
    app_version,
    user_id is null as is_anonymous,
    -- Device clocks set wrong: the event claims to happen after it was received.
    coalesce({{ dbt.datediff('received_at', 'event_ts', 'second') }} > 86400, false) as is_clock_skewed
from deduped
