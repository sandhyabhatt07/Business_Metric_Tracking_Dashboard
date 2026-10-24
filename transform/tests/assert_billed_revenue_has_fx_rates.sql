-- Every invoice must convert to USD: an invoice dropped by a missing rate would understate revenue.
select i.invoice_id
from {{ ref('stg_app__invoices') }} as i
left join {{ ref('fct_invoices') }} as f on i.invoice_id = f.invoice_id
where f.invoice_id is null
