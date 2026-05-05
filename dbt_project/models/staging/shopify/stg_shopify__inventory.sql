-- Renames and casts raw daily inventory positions.
-- Staging rule: rename, cast, filter only. No business logic.
-- low_stock_flag and days_of_stock_remaining are defined in mart_inventory.

with source as (

    select * from {{ source('shopify', 'shopify_inventory') }}

),

renamed as (

    select
        sku,
        cast(date as date)                 as inventory_date,
        cast(inventory_quantity as int64)  as inventory_quantity,
        cast(was_out_of_stock as bool)     as was_out_of_stock

    from source

)

select
    sku,
    inventory_date,
    inventory_quantity,
    was_out_of_stock
from renamed
