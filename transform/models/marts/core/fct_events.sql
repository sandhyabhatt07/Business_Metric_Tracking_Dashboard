{{ config(partition_by=bq_partition('event_date'),
          cluster_by=['event_name', 'user_id'] if target.type == 'bigquery' else none) }}

-- Governed product events: deduplicated, with anonymous, clock-skewed and internal activity removed.
select
    e.event_id,
    e.event_ts,
    e.event_date,
    e.user_id,
    u.account_id,
    e.session_id,
    e.event_name,
    e.platform,
    e.app_version
from {{ ref('stg_app__events') }} as e
inner join {{ ref('stg_app__users') }} as u on e.user_id = u.user_id
where not e.is_anonymous
    and not e.is_clock_skewed
    and not u.is_internal
