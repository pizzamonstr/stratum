-- Renames and casts raw Klaviyo email events.
-- Staging rule: rename, cast, filter only. No business logic.

with source as (

    select * from {{ source('marketing', 'klaviyo_email_events') }}

),

renamed as (

    select
        event_id,
        email_id,
        email_name,
        flow_name,
        contact_id,
        event_type,
        cast(occurred_at as timestamp)                  as occurred_at,
        cast(klaviyo_reported_revenue as float64)     as klaviyo_reported_revenue,
        case
            when flow_name is not null then 'flow'
            else 'campaign'
        end                                             as email_type

    from source

)

select
    event_id,
    email_id,
    email_name,
    flow_name,
    contact_id,
    event_type,
    occurred_at,
    klaviyo_reported_revenue,
    email_type
from renamed
