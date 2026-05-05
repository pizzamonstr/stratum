-- Monthly revenue split by customer_type (new vs returning).
-- One row per month per customer_type. Used in every executive summary.
-- Deduplicates to order grain before aggregating to avoid double-counting
-- net_revenue across line items.

with line_item_grain as (

    select * from {{ ref('mart_orders') }}

),

-- Deduplicate to order level for revenue and order count
order_grain as (

    select distinct
        order_id,
        customer_id,
        ordered_at,
        net_revenue,
        customer_type

    from line_item_grain

),

monthly as (

    select
        date_trunc(date(ordered_at), month)     as order_month,
        customer_type,
        count(distinct order_id)                as orders,
        count(distinct customer_id)             as customers,
        sum(net_revenue)                        as net_revenue,
        round(
            sum(net_revenue)
            / nullif(count(distinct order_id), 0),
            2
        )                                       as avg_order_value

    from order_grain
    group by
        date_trunc(date(ordered_at), month),
        customer_type

)

select
    order_month,
    customer_type,
    orders,
    customers,
    net_revenue,
    avg_order_value
from monthly
order by order_month, customer_type
