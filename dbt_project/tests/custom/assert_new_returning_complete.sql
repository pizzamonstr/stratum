-- assert_new_returning_complete.sql
-- The sum of new + returning customers in mart_new_vs_returning must equal
-- the distinct customer count in mart_orders for every month.
-- Any row returned indicates a customer_type mapping gap.

with typed_totals as (

    select
        order_month,
        sum(customers) as customers_by_type

    from {{ ref('mart_new_vs_returning') }}
    group by order_month

),

actual_totals as (

    select
        date_trunc(date(ordered_at), month)   as order_month,
        count(distinct customer_id)           as total_customers

    from {{ ref('mart_orders') }}
    group by date_trunc(date(ordered_at), month)

)

select
    typed_totals.order_month,
    typed_totals.customers_by_type,
    actual_totals.total_customers

from typed_totals
inner join actual_totals
    on typed_totals.order_month = actual_totals.order_month
where abs(typed_totals.customers_by_type - actual_totals.total_customers) > 0
