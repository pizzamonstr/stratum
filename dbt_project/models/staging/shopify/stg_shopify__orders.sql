-- Renames, casts, and filters raw Shopify orders.
-- Staging rule: rename, cast, filter only. No business logic.
-- net_revenue is defined in mart_orders using the net_revenue macro.

with source as (

    select * from {{ source('shopify', 'shopify_orders') }}

),

renamed as (

    select
        order_id,
        customer_id,
        cast(created_at as timestamp)                 as ordered_at,
        financial_status,
        cast(gross_revenue as float64)                as gross_revenue,
        cast(coalesce(discount_amount, 0) as float64) as discount_amount,
        acquisition_channel,
        shipping_country,
        cast(test_order as bool)                      as test_order

    from source
    where financial_status not in ('voided', 'pending')
      and cast(test_order as bool) = false

)

select
    order_id,
    customer_id,
    ordered_at,
    financial_status,
    gross_revenue,
    discount_amount,
    acquisition_channel,
    shipping_country
from renamed
