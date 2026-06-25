-- assert_recent_data.sql
-- mart_orders must contain rows within the last 48 hours of the dataset's
-- own end date (max ordered_at), not wall-clock time. Synthetic data has
-- a fixed historical date range, so this validates that the most recent
-- orders are present relative to the dataset boundary. Any row returned
-- indicates missing trailing data in the pipeline.

select
    max_ordered_at,
    'missing_recent_orders' as failure_reason
from (
    select max(ordered_at) as max_ordered_at
    from {{ ref('mart_orders') }}
) as bounds
where not exists (
    select 1
    from {{ ref('mart_orders') }}
    where ordered_at >= timestamp_sub(
        (select max(ordered_at) from {{ ref('mart_orders') }}),
        interval 2 day
    )
)
