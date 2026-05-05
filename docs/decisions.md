# Decisions

## Business logic lives in the mart layer

One definition of net_revenue, customer_type, and customer_segment.
Changing a KPI definition means editing one SQL file. Staging models
rename, cast, and filter only.

## net_revenue calculated via macro

The net_revenue macro enforces a single definition. It cannot silently
diverge between mart_orders and mart_revenue_summary.

## Staging models are views; marts are tables

Views keep raw data accessible without storage cost.
Tables make dashboard queries fast and consistent.

## Order-level deduplication in customer aggregations

mart_orders is at line item grain. net_revenue is an order-level
field repeated across line items. Customer and cohort models use
select distinct on order-level fields before aggregating to avoid
inflating revenue totals.

## Incremental materialisation on mart_orders and mart_cohort_analysis

Minimises BigQuery compute cost as data volume grows.
Both use merge strategy with a stable unique key.

## Platform attribution is not used for cross-channel ROAS

Meta, Google, and Klaviyo all overclaim conversions. Blended ROAS
uses Shopify net_revenue only. Platform-reported figures are stored
and clearly labelled but do not enter any blended calculation.
