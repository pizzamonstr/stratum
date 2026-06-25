-- Daily last-touch attribution by acquisition channel.
-- One row per acquisition_channel per date. Shopify net_revenue is the
-- source of truth for channel revenue. Platform-reported conversions are
-- not used. Paid spend is joined from Meta (all audience types) and Google
-- (all campaign types) at daily grain.

with line_item_grain as (

    select * from {{ ref('mart_orders') }}

),

order_grain as (

    select distinct
        order_id,
        date(ordered_at)            as date,
        acquisition_channel,
        net_revenue,
        customer_type

    from line_item_grain

),

daily_channel_revenue as (

    select
        date,
        acquisition_channel,
        count(distinct order_id)    as shopify_orders,
        sum(net_revenue)            as shopify_revenue,
        sum(
            case
                when customer_type = 'new' then net_revenue
                else 0
            end
        )                           as new_customer_revenue,
        sum(
            case
                when customer_type = 'returning' then net_revenue
                else 0
            end
        )                           as returning_customer_revenue

    from order_grain
    group by
        date,
        acquisition_channel

),

meta_daily as (

    select
        date,
        sum(spend)                  as meta_spend

    from {{ ref('stg_meta__ad_insights') }}
    group by date

),

google_daily as (

    select
        date,
        sum(spend)                  as google_spend

    from {{ ref('stg_google__performance') }}
    group by date

),

all_dates as (

    select date from daily_channel_revenue
    union distinct
    select date from meta_daily
    union distinct
    select date from google_daily

),

channels as (

    select acquisition_channel
    from unnest([
        'paid_social',
        'paid_search',
        'organic',
        'email',
        'direct'
    ]) as acquisition_channel

),

date_channel_spine as (

    select
        all_dates.date,
        channels.acquisition_channel

    from all_dates
    cross join channels

),

joined as (

    select
        date_channel_spine.date,
        date_channel_spine.acquisition_channel,

        coalesce(daily_channel_revenue.shopify_orders, 0)
                                        as shopify_orders,
        coalesce(daily_channel_revenue.shopify_revenue, 0)
                                        as shopify_revenue,

        case
            when date_channel_spine.acquisition_channel = 'paid_social'
            then meta_daily.meta_spend
        end                             as meta_spend,

        case
            when date_channel_spine.acquisition_channel = 'paid_search'
            then google_daily.google_spend
        end                             as google_spend,

        coalesce(meta_daily.meta_spend, 0)
            + coalesce(google_daily.google_spend, 0)
                                        as total_paid_spend,

        coalesce(daily_channel_revenue.new_customer_revenue, 0)
                                        as new_customer_revenue,
        coalesce(daily_channel_revenue.returning_customer_revenue, 0)
                                        as returning_customer_revenue

    from date_channel_spine
    left join daily_channel_revenue
        on date_channel_spine.date = daily_channel_revenue.date
        and date_channel_spine.acquisition_channel
            = daily_channel_revenue.acquisition_channel
    left join meta_daily
        on date_channel_spine.date = meta_daily.date
    left join google_daily
        on date_channel_spine.date = google_daily.date

)

select
    date,
    acquisition_channel,
    shopify_orders,
    shopify_revenue,
    meta_spend,
    google_spend,
    total_paid_spend,
    round(
        shopify_revenue / nullif(total_paid_spend, 0),
        2
    )                                   as blended_roas,
    new_customer_revenue,
    returning_customer_revenue
from joined
order by date, acquisition_channel
