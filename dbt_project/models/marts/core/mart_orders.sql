{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='line_item_id'
    )
}}

-- Order line item spine. One row per line item.
-- All downstream mart models join back to this.
-- net_revenue and customer_type are resolved here.

with line_items as (

    select * from {{ ref('stg_shopify__order_line_items') }}

),

orders as (

    select * from {{ ref('stg_shopify__orders') }}

    {% if is_incremental() %}
        where ordered_at > (select max(ordered_at) from {{ this }})
    {% endif %}

),

customers as (

    select * from {{ ref('stg_shopify__customers') }}

),

-- Rank each order per customer to identify first (new) vs subsequent (returning)
customer_order_ranks as (

    select
        order_id,
        customer_id,
        ordered_at,
        row_number() over (
            partition by customer_id
            order by ordered_at
        )                   as order_rank,
        lag(ordered_at) over (
            partition by customer_id
            order by ordered_at
        )                   as prior_order_at

    from orders

),

joined as (

    select
        line_items.line_item_id,
        orders.order_id,
        orders.customer_id,
        orders.ordered_at,
        orders.financial_status,
        orders.gross_revenue,
        orders.discount_amount,

        -- Single agreed net_revenue definition, enforced via macro
        {{ net_revenue('orders.gross_revenue', 'orders.discount_amount') }}
                                as net_revenue,

        orders.acquisition_channel,
        orders.shipping_country,

        line_items.sku,
        line_items.product_title,
        line_items.product_category,
        line_items.quantity,
        line_items.unit_price,
        line_items.line_revenue,

        customers.email         as customer_email,
        customers.city          as customer_city,
        customers.country       as customer_country,

        -- 'new' on first order; 'returning' on all subsequent orders
        case
            when customer_order_ranks.order_rank = 1 then 'new'
            else 'returning'
        end                     as customer_type,

        -- null for first orders; days since prior order for repeats
        case
            when customer_order_ranks.prior_order_at is not null
            then date_diff(
                date(orders.ordered_at),
                date(customer_order_ranks.prior_order_at),
                day
            )
        end                     as days_since_prior_order

    from line_items
    inner join orders
        on line_items.order_id = orders.order_id
    inner join customers
        on orders.customer_id = customers.customer_id
    inner join customer_order_ranks
        on orders.order_id = customer_order_ranks.order_id

)

select
    line_item_id,
    order_id,
    customer_id,
    ordered_at,
    financial_status,
    gross_revenue,
    discount_amount,
    net_revenue,
    acquisition_channel,
    shipping_country,
    sku,
    product_title,
    product_category,
    quantity,
    unit_price,
    line_revenue,
    customer_email,
    customer_city,
    customer_country,
    customer_type,
    days_since_prior_order
from joined
