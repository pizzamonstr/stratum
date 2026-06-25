-- Customer-level lifetime summary. One row per customer.
-- Derived from mart_orders. net_revenue is an order-level field repeated
-- across line items, so we deduplicate to order grain before summing
-- to avoid inflating revenue and order counts.

with line_item_grain as (

    select * from {{ ref('mart_orders') }}

),

-- Order-level deduplication for revenue and order count aggregations
order_grain as (

    select distinct
        order_id,
        customer_id,
        ordered_at,
        net_revenue,
        acquisition_channel,
        customer_type,
        customer_email,
        customer_country

    from line_item_grain

),

-- Acquisition channel from each customer's first order
first_order_channels as (

    select
        customer_id,
        acquisition_channel as acquisition_channel_first

    from order_grain
    where customer_type = 'new'

),

-- Revenue per category per customer (uses line item grain for accuracy)
category_revenue as (

    select
        customer_id,
        product_category,
        sum(line_revenue) as total_category_revenue

    from line_item_grain
    group by customer_id, product_category

),

-- Rank categories per customer to find the highest-revenue one
category_ranked as (

    select
        customer_id,
        product_category,
        row_number() over (
            partition by customer_id
            order by total_category_revenue desc
        ) as revenue_rank

    from category_revenue

),

top_category as (

    select
        customer_id,
        product_category as favourite_category

    from category_ranked
    where revenue_rank = 1

),

customer_summary as (

    select
        order_grain.customer_id,
        order_grain.customer_email,
        order_grain.customer_country,
        min(order_grain.ordered_at)                     as first_order_at,
        max(order_grain.ordered_at)                     as most_recent_order_at,
        count(distinct order_grain.order_id)            as total_orders,
        sum(order_grain.net_revenue)                    as total_revenue,
        round(
            sum(order_grain.net_revenue)
            / nullif(count(distinct order_grain.order_id), 0),
            2
        )                                               as avg_order_value,
        date_diff(
            current_date(),
            date(max(order_grain.ordered_at)),
            day
        )                                               as days_since_last_order,
        date_diff(
            current_date(),
            date(min(order_grain.ordered_at)),
            day
        )                                               as days_since_first_order,
        first_order_channels.acquisition_channel_first,
        top_category.favourite_category,

        -- Segment driven by lifetime order count
        case
            when count(distinct order_grain.order_id) = 1
                then 'one_time'
            when count(distinct order_grain.order_id) between 2 and 4
                then 'occasional'
            else 'loyal'
        end                                             as customer_segment

    from order_grain
    left join first_order_channels
        on order_grain.customer_id = first_order_channels.customer_id
    left join top_category
        on order_grain.customer_id = top_category.customer_id
    group by
        order_grain.customer_id,
        order_grain.customer_email,
        order_grain.customer_country,
        first_order_channels.acquisition_channel_first,
        top_category.favourite_category

)

select
    customer_id,
    customer_email,
    customer_country,
    first_order_at,
    most_recent_order_at,
    total_orders,
    total_revenue,
    avg_order_value,
    days_since_last_order,
    days_since_first_order,
    acquisition_channel_first,
    favourite_category,
    customer_segment
from customer_summary
