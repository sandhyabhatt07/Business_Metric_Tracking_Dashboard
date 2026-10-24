-- Weekly user retention: of users who signed up in a week, how many were active N weeks later
-- (weeks counted from each user's own signup date). Cells that haven't fully happened yet are
-- flagged with is_complete = false.
with users as (
    select user_id, signup_date, signup_week, segment
    from {{ ref('dim_user') }}
    where not is_internal and signup_date <= {{ as_of_date() }}
),

weeks as (
    select generated_number - 1 as week_number
    from ({{ dbt_utils.generate_series(27) }}) as s
),

activity as (
    select distinct
        u.user_id,
        cast(floor({{ dbt.datediff('u.signup_date', 'a.activity_date', 'day') }} / 7) as {{ dbt.type_int() }})
            as week_number
    from {{ ref('fct_user_daily_activity') }} as a
    inner join users as u on a.user_id = u.user_id
),

cohorts as (
    select signup_week, segment, count(*) as cohort_users
    from users
    group by 1, 2
),

active as (
    select u.signup_week, u.segment, a.week_number, count(*) as active_users
    from activity as a
    inner join users as u on a.user_id = u.user_id
    group by 1, 2, 3
)

select
    c.signup_week,
    c.segment,
    w.week_number,
    c.cohort_users,
    coalesce(a.active_users, 0) as active_users,
    coalesce(a.active_users, 0) / c.cohort_users as retention_rate,
    -- Complete once the cohort's last signup (week start + 6 days) has lived through all of week N.
    {{ add_days('c.signup_week', '(w.week_number * 7 + 12)') }} <= {{ as_of_date() }} as is_complete
from cohorts as c
cross join weeks as w
left join active as a
    on c.signup_week = a.signup_week and c.segment = a.segment and w.week_number = a.week_number
