-- Daily inventory positions with demand metrics and risk flags.
-- One row per SKU per day.
-- low_stock_flag and days_of_stock_remaining are defined here,
-- not in the staging model.

with inventory as (

    select * from {{ ref('stg_shopify__inventory') }}

),

-- Daily units sold per SKU from the order line item spine
daily_sales as (

    select
        sku,
        date(ordered_at)    as sales_date,
        sum(quantity)       as units_sold

    from {{ ref('mart_orders') }}
    group by sku, date(ordered_at)

),

-- Join inventory snapshot to that day's sales
joined as (

    select
        inventory.sku,
        inventory.inventory_date,
        inventory.inventory_quantity,
        inventory.was_out_of_stock,
        coalesce(daily_sales.units_sold, 0) as units_sold_that_day

    from inventory
    left join daily_sales
        on inventory.sku = daily_sales.sku
        and inventory.inventory_date = daily_sales.sales_date

),

-- Compute rolling 30-day average in a separate CTE.
-- BigQuery does not support nested window functions.
with_rolling_avg as (

    select
        sku,
        inventory_date,
        inventory_quantity,
        was_out_of_stock,
        units_sold_that_day,

        -- low_stock_flag defined here using the project variable
        inventory_quantity < {{ var('low_stock_threshold') }}
                                        as low_stock_flag,

        avg(cast(units_sold_that_day as float64)) over (
            partition by sku
            order by inventory_date
            rows between 29 preceding and current row
        )                               as avg_daily_sales_rate_30d

    from joined

)

select
    sku,
    inventory_date,
    inventory_quantity,
    was_out_of_stock,
    low_stock_flag,
    units_sold_that_day,
    round(avg_daily_sales_rate_30d, 2)  as avg_daily_sales_rate_30d,
    round(
        safe_divide(
            cast(inventory_quantity as float64),
            nullif(avg_daily_sales_rate_30d, 0)
        ),
        1
    )                                   as days_of_stock_remaining
from with_rolling_avg
