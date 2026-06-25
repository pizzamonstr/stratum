-- Renames and casts raw Google Ads performance.
-- Staging rule: rename, cast, filter only. No business logic.

with source as (

    select * from {{ source('marketing', 'google_performance') }}

),

renamed as (

    select
        campaign_id,
        campaign_name,
        campaign_type,
        ad_group_id,
        ad_group_name,
        cast(date as date)                            as date,
        cast(spend as float64)                        as spend,
        cast(impressions as int64)                    as impressions,
        cast(clicks as int64)                         as clicks,
        cast(avg_cpc as float64)                      as avg_cpc,
        cast(impression_share as float64)             as impression_share,
        cast(lost_impression_share_budget as float64)
                                                        as lost_impression_share_budget,
        cast(platform_reported_conversions as float64)
                                                        as google_reported_conversions,
        cast(platform_reported_revenue as float64)    as google_reported_revenue,
        'google'                                      as platform

    from source

)

select
    campaign_id,
    campaign_name,
    campaign_type,
    ad_group_id,
    ad_group_name,
    date,
    spend,
    impressions,
    clicks,
    avg_cpc,
    impression_share,
    lost_impression_share_budget,
    google_reported_conversions,
    google_reported_revenue,
    platform
from renamed
