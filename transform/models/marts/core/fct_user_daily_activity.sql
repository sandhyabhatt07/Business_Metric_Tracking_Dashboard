{{ config(partition_by=bq_partition('activity_date'),
          cluster_by=['account_id'] if target.type == 'bigquery' else none) }}

-- One row per user per day they were active. Every event in fct_events counts as activity.
select
    user_id,
    account_id,
    event_date as activity_date,
    count(*) as events,
    count(distinct session_id) as sessions,
    sum(case when event_name = 'create_report' or event_name = 'report_created' then 1 else 0 end) as reports_created
from {{ ref('fct_events') }}
group by 1, 2, 3
