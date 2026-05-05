-- Renames and casts raw Shopify customer fields.
-- Staging rule: rename, cast, filter only. No business logic.
-- days_since_last_order is calculated in mart_customers.

with source as (

    select * from {{ source('shopify', 'shopify_customers') }}

),

renamed as (

    select
        customer_id,
        email,
        cast(created_at as timestamp) as created_at,
        city,
        region,
        country,
        cast(total_orders as int64)   as total_orders,
        cast(total_spent as float64)  as total_spent

    from source

)

select
    customer_id,
    email,
    created_at,
    city,
    region,
    country,
    total_orders,
    total_spent
from renamed
