-- A new segment spelling in the CRM must be added to seeds/segment_mapping.csv before it can flow
-- into reporting, otherwise those accounts would silently fall into "Unknown".
select segment_raw, count(*) as companies
from {{ ref('stg_crm__companies') }}
where segment = 'Unknown' and segment_raw is not null
group by 1
