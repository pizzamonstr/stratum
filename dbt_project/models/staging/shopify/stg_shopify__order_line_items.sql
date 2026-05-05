-- Renames and casts raw Shopify order line item fields.

with source as (

    select * from {{ source('shopify', 'shopify_order_line_items') }}

),

renamed as (

    select
        line_item_id,
        order_id,
        sku,
        product_title,
        product_category,
        cast(quantity as int64)       as quantity,
        cast(unit_price as float64)   as unit_price,
        cast(line_revenue as float64) as line_revenue

    from source

)

select
    line_item_id,
    order_id,
    sku,
    product_title,
    product_category,
    quantity,
    unit_price,
    line_revenue
from renamed
