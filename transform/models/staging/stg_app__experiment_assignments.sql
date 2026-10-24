select
    user_id,
    experiment_name,
    variant,
    assigned_at
from {{ source('raw', 'app_experiment_assignments') }}
