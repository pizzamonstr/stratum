-- Monthly blended ROAS. One row per month.
-- The single agreed monthly ROAS figure for marketing reporting.
-- Aggregated from mart_attribution using Shopify net_revenue as the
-- numerator and total paid spend (Meta + Google) as the denominator.

with daily_attribution as (

    select * from {{ ref('mart_attribution') }}

),

monthly as (

    select
        date_trunc(date, month)         as month,
        sum(shopify_revenue)            as total_shopify_revenue,
        sum(coalesce(meta_spend, 0))    as meta_spend,
        sum(coalesce(google_spend, 0))  as google_spend,
        sum(new_customer_revenue)       as new_customer_revenue,
        sum(returning_customer_revenue) as returning_customer_revenue

    from daily_attribution
    group by date_trunc(date, month)

),

with_roas as (

    select
        month,
        total_shopify_revenue,
        meta_spend + google_spend       as total_paid_spend,
        meta_spend,
        google_spend,
        new_customer_revenue,
        returning_customer_revenue,
        round(
            total_shopify_revenue / nullif(meta_spend + google_spend, 0),
            2
        )                               as blended_roas,
        round(
            new_customer_revenue
                / nullif(meta_spend + google_spend, 0),
            2
        )                               as new_customer_roas,
        round(
            returning_customer_revenue
                / nullif(meta_spend + google_spend, 0),
            2
        )                               as returning_customer_roas

    from monthly

)

select
    month,
    total_shopify_revenue,
    total_paid_spend,
    blended_roas,
    meta_spend,
    google_spend,
    new_customer_revenue,
    returning_customer_revenue,
    new_customer_roas,
    returning_customer_roas
from with_roas
order by month
