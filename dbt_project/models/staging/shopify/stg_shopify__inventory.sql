-- Renames and casts raw daily inventory positions.
-- Staging rule: rename, cast, filter only. No business logic.
-- low_stock is a simple boolean derived from quantity vs the configured
-- threshold. days_of_stock_remaining and rolling averages live in mart_inventory.

with source as (

    select * from {{ source('shopify', 'shopify_inventory') }}

),

renamed as (

    select
        sku,
        cast(date as date)                as inventory_date,
        cast(inventory_quantity as int64)   as inventory_quantity,
        cast(inventory_quantity as int64) = 0
                                            as was_out_of_stock,
        cast(inventory_quantity as int64) < {{ var('low_stock_threshold') }}
                                            as low_stock

    from source

)

select
    sku,
    inventory_date,
    inventory_quantity,
    was_out_of_stock,
    low_stock
from renamed
