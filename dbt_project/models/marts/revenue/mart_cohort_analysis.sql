{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='cohort_key'
    )
}}

-- Customer cohort retention table.
-- One row per cohort_month × months_since_first_purchase.
-- Answers: how do customers acquired in a given month spend over time?

with line_item_grain as (

    select * from {{ ref('mart_orders') }}

),

-- Deduplicate to order level before cohort aggregation
order_grain as (

    select distinct
        order_id,
        customer_id,
        ordered_at,
        net_revenue

    from line_item_grain

),

-- Assign each customer to the month of their first order
first_orders as (

    select
        customer_id,
        date_trunc(date(min(ordered_at)), month) as cohort_month

    from order_grain
    group by customer_id

),

cohort_data as (

    select
        first_orders.cohort_month,
        date_diff(
            date_trunc(date(order_grain.ordered_at), month),
            first_orders.cohort_month,
            month
        )                                           as months_since_first_purchase,
        count(distinct order_grain.customer_id)     as customers_active,
        sum(order_grain.net_revenue)                as revenue,
        round(
            sum(order_grain.net_revenue)
            / nullif(count(distinct order_grain.customer_id), 0),
            2
        )                                           as avg_revenue_per_customer

    from first_orders
    inner join order_grain
        on first_orders.customer_id = order_grain.customer_id
    group by
        first_orders.cohort_month,
        months_since_first_purchase

),

-- Stable composite key for incremental merge
keyed as (

    select
        concat(
            cast(cohort_month as string),
            '-',
            cast(months_since_first_purchase as string)
        )                           as cohort_key,
        cohort_month,
        months_since_first_purchase,
        customers_active,
        revenue,
        avg_revenue_per_customer

    from cohort_data

    {% if is_incremental() %}
        -- Only reprocess cohorts with potential new activity
        where cohort_month >= date_trunc(
            date_sub(current_date(), interval 3 month),
            month
        )
    {% endif %}

)

select
    cohort_key,
    cohort_month,
    months_since_first_purchase,
    customers_active,
    revenue,
    avg_revenue_per_customer
from keyed
