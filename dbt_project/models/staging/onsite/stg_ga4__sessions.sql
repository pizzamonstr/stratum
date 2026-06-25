-- Renames and casts raw GA4 session data.
-- Staging rule: rename, cast, filter only. No business logic.

with source as (

    select * from {{ source('marketing', 'ga4_sessions') }}

),

renamed as (

    select
        session_id,
        ga4_client_id,
        cast(session_date as date)                    as session_date,
        acquisition_channel,
        acquisition_source,
        acquisition_medium,
        landing_page,
        cast(session_duration_seconds as int64)       as session_duration_seconds,
        cast(pages_viewed as int64)                   as pages_viewed,
        cast(add_to_cart_events as int64)             as add_to_cart_events,
        cast(checkout_started as int64)               as checkout_started,
        cast(shopify_order_id as string)              as shopify_order_id

    from source

)

select
    session_id,
    ga4_client_id,
    session_date,
    acquisition_channel,
    acquisition_source,
    acquisition_medium,
    landing_page,
    session_duration_seconds,
    pages_viewed,
    add_to_cart_events,
    checkout_started,
    shopify_order_id
from renamed
