-- One row per app account: the latest-modified CRM record wins, and segment spellings are normalised.
with parsed as (
    select
        crm_company_id,
        cast(app_account_id as {{ dbt.type_int() }}) as account_id,
        name as company_name,
        lower(trim(segment)) as segment_raw,
        cast(numberofemployees as {{ dbt.type_int() }}) as employee_count,
        industry,
        region,
        country,
        hubspot_owner as crm_owner,
        lifecyclestage as lifecycle_stage,
        {{ parse_iso_timestamp('createdate') }} as crm_created_at,
        {{ parse_iso_timestamp('lastmodifieddate') }} as crm_modified_at
    from {{ source('raw', 'crm_companies') }}
),

latest as (
    {{ dedupe('parsed', 'account_id', 'crm_modified_at desc, crm_company_id desc') }}
)

select
    latest.*,
    coalesce(m.segment, 'Unknown') as segment
from latest
left join {{ ref('segment_mapping') }} as m
    on latest.segment_raw = m.raw_segment
