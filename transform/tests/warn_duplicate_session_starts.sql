{{ config(severity='warn') }}

-- Every session should log exactly one session_start. Days where many sessions log more point to a
-- client tracking bug (like the January 2026 iOS double-fire): event counts are inflated even though
-- deduplication by event_id can't catch it. DAU is unaffected because it counts distinct users.
with per_session as (
    select event_date, platform, session_id, count(*) as starts
    from {{ ref('stg_app__events') }}
    where event_name = 'session_start' and not is_clock_skewed
    group by 1, 2, 3
)

select
    event_date,
    platform,
    count(*) as sessions,
    sum(case when starts > 1 then 1 else 0 end) as sessions_with_repeat_starts
from per_session
group by 1, 2
having sum(case when starts > 1 then 1 else 0 end) > 0.01 * count(*)
