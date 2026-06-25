-- Monthly revenue by product category, acquisition channel, and shipping country.
-- One row per month per product_category per acquisition_channel per
-- shipping_country. Order-level net_revenue is allocated to line items
-- proportionally by line_revenue share to avoid double-counting across
-- categories while preserving the agreed net_revenue definition.

with line_item_grain as (

    select * from {{ ref('mart_orders') }}

),

order_totals as (

    select
        order_id,
        max(net_revenue)          as net_revenue,
        max(customer_id)          as customer_id,
        max(ordered_at)           as ordered_at,
        max(acquisition_channel)  as acquisition_channel,
        max(shipping_country)     as shipping_country

    from line_item_grain
    group by order_id

),

line_with_share as (

    select
        line_item_grain.order_id,
        line_item_grain.customer_id,
        line_item_grain.ordered_at,
        line_item_grain.product_category,
        line_item_grain.acquisition_channel,
        line_item_grain.shipping_country,
        safe_divide(
            line_item_grain.line_revenue,
            sum(line_item_grain.line_revenue) over (
                partition by line_item_grain.order_id
            )
        )                           as revenue_share

    from line_item_grain

),

allocated as (

    select
        line_with_share.order_id,
        line_with_share.customer_id,
        line_with_share.ordered_at,
        line_with_share.product_category,
        line_with_share.acquisition_channel,
        line_with_share.shipping_country,
        order_totals.net_revenue
            * line_with_share.revenue_share              as revenue

    from line_with_share
    inner join order_totals
        on line_with_share.order_id = order_totals.order_id

),

monthly as (

    select
        date_trunc(date(ordered_at), month)              as month,
        product_category,
        acquisition_channel,
        shipping_country,
        count(distinct order_id)                        as orders,
        count(distinct customer_id)                     as customers,
        round(sum(revenue), 2)                          as revenue,
        round(
            sum(revenue) / nullif(count(distinct order_id), 0),
            2
        )                                               as avg_order_value

    from allocated
    group by
        month,
        product_category,
        acquisition_channel,
        shipping_country

)

select
    month,
    product_category,
    acquisition_channel,
    shipping_country,
    orders,
    customers,
    revenue,
    avg_order_value
from monthly
order by
    month,
    product_category,
    acquisition_channel,
    shipping_country
