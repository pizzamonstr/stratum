-- assert_recent_data.sql
-- mart_orders must contain rows from within the last 48 hours.
-- Any result indicates a stale or failed sync.
-- Only active in prod (STRATUM_ENV=prod) to avoid false failures
-- on synthetic data, which has a fixed historical date range.

select 'stale_pipeline' as failure_reason
where not exists (
    select 1
    from {{ ref('mart_orders') }}
    where ordered_at >= timestamp_sub(current_timestamp(), interval 48 hour)
)
  and '{{ env_var("STRATUM_ENV", "dev") }}' = 'prod'
