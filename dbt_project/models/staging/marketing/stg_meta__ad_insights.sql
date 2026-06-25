-- Renames and casts raw Meta ad insights.
-- Staging rule: rename, cast, filter only. No business logic.

with source as (

    select * from {{ source('marketing', 'meta_ad_insights') }}

),

renamed as (

    select
        campaign_id,
        campaign_name,
        campaign_objective,
        adset_id,
        adset_name,
        audience_type,
        cast(date as date)                            as date,
        cast(spend as float64)                        as spend,
        cast(impressions as int64)                    as impressions,
        cast(clicks as int64)                         as clicks,
        cast(reach as int64)                          as reach,
        cast(frequency as float64)                    as frequency,
        cast(platform_reported_conversions as float64)
                                                        as meta_reported_conversions,
        cast(platform_reported_revenue as float64)    as meta_reported_revenue,
        'meta'                                        as platform

    from source

)

select
    campaign_id,
    campaign_name,
    campaign_objective,
    adset_id,
    adset_name,
    audience_type,
    date,
    spend,
    impressions,
    clicks,
    reach,
    frequency,
    meta_reported_conversions,
    meta_reported_revenue,
    platform
from renamed
