select plan, tier_rank, list_price_usd_per_seat, min_seats
from {{ ref('plans') }}
