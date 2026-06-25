-- Monthly revenue split by customer_type (new vs returning).
-- One row per month per customer_type. Used in every executive summary.
-- Deduplicates to order grain before aggregating to avoid double-counting
-- net_revenue across line items.
-- Customer type is assigned once per customer per month: 'new' in the month
-- of their first order; 'returning' in all subsequent active months.

with line_item_grain as (

    select * from {{ ref('mart_orders') }}

),

order_grain as (

    select distinct
        order_id,
        customer_id,
        ordered_at,
        net_revenue

    from line_item_grain

),

customer_first_order as (

    select
        customer_id,
        date_trunc(date(min(ordered_at)), month) as first_order_month

    from order_grain
    group by customer_id

),

orders_with_month_type as (

    select
        order_grain.order_id,
        order_grain.customer_id,
        order_grain.net_revenue,
        date_trunc(date(order_grain.ordered_at), month) as month,
        case
            when date_trunc(date(order_grain.ordered_at), month)
                = customer_first_order.first_order_month
            then 'new'
            else 'returning'
        end                                             as customer_type

    from order_grain
    inner join customer_first_order
        on order_grain.customer_id = customer_first_order.customer_id

),

monthly as (

    select
        month,
        customer_type,
        count(distinct order_id)                as orders,
        count(distinct customer_id)             as customers,
        sum(net_revenue)                        as revenue,
        round(
            sum(net_revenue)
            / nullif(count(distinct order_id), 0),
            2
        )                                       as avg_order_value

    from orders_with_month_type
    group by
        month,
        customer_type

)

select
    month,
    customer_type,
    orders,
    customers,
    revenue,
    avg_order_value
from monthly
order by month, customer_type
