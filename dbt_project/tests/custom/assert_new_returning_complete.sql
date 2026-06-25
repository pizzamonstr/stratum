-- assert_new_returning_complete.sql
-- New + returning customer counts in mart_new_vs_returning must equal the
-- total distinct customer count per month in mart_orders. A mismatch means
-- some orders are missing a customer_type assignment or are being double-counted
-- in the monthly aggregation.

with order_customers_by_month as (

    select
        date_trunc(date(ordered_at), month) as month,
        count(distinct customer_id)         as total_customers

    from {{ ref('mart_orders') }}
    group by month

),

new_returning_by_month as (

    select
        month,
        sum(customers) as new_returning_customers

    from {{ ref('mart_new_vs_returning') }}
    group by month

)

select
    order_customers_by_month.month,
    order_customers_by_month.total_customers,
    new_returning_by_month.new_returning_customers

from order_customers_by_month
inner join new_returning_by_month
    on order_customers_by_month.month = new_returning_by_month.month
where order_customers_by_month.total_customers
    != new_returning_by_month.new_returning_customers
