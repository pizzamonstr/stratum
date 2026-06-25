# Limitations

## Attribution is last-touch only

The pipeline uses last-touch attribution via the Shopify acquisition_channel
field. This overstates bottom-of-funnel channels (paid search, email) and
understates upper-funnel channels (paid social).

## Amazon customer identity is permanently obscured

If a Conduit client sells on Amazon, cross-channel customer matching is not
possible. Amazon orders are revenue-only with no customer ID.

## GA4 source is session-level, not event-level

The synthetic GA4 model uses session-level grain. A real Conduit
implementation uses the full event-level BigQuery export, which is
significantly more complex.

## Pipeline is nightly, not real-time

Dashboards reflect the previous day's data. The assert_recent_data
test detects stale syncs before anyone opens a dashboard.

## LLM parsing failures (Checkpoint B+)

Some reviews and tickets will fail to parse. The parse_failure_rate
test alerts if failures exceed 10% in any week. Failed parses are
flagged with parse_failed = true and raw text is retained for
reprocessing if parsing logic improves.

## Incremental filter scope in mart_orders

The incremental filter in `mart_orders` is applied to the `orders` CTE only.
The `order_line_items` CTE is fully scanned on every incremental run and joined
down to new orders via the merge on `line_item_id`. This is logically correct
but inefficient at scale. For a Conduit implementation on real data, the line
items CTE should carry a matching date filter to avoid a full table scan.

## mart_revenue_summary is a stub in Checkpoint A

mart_revenue_summary was scaffolded in Checkpoint A but not fully implemented.
The Revenue dashboard detects this at runtime and falls back to mart_orders for
category and channel breakdowns. This fallback will be removed when
mart_revenue_summary is properly built in Checkpoint B with product_category,
acquisition_channel, and revenue columns populated.

## Revenue dashboard fallback pulls full mart_orders into memory

When mart_revenue_summary is not populated, the Revenue page loads the entire
mart_orders table into a pandas DataFrame to compute category and channel
breakdowns. This is acceptable at Stratum's synthetic data volumes but would
be slow and expensive on a real dataset. For a Conduit implementation, either
build mart_revenue_summary properly before connecting the dashboard, or push
the aggregation into a BigQuery query rather than doing it in pandas.

## Attribution overclaim multipliers are not stored per row

The attribution overclaim multipliers used during synthetic data generation
are configured as ranges in synthetic_config.yml but are not recorded as
fields in the raw marketing tables. The overclaiming pattern is visible in
aggregate (platform_reported_conversions vs Shopify actuals) but the exact
multiplier applied to any individual row cannot be recovered from the data.
For a Conduit implementation this is not relevant -- real platform data is
used directly and overclaiming is observed rather than simulated.

## Synthetic campaign conversion share is distributed evenly

In generate_meta_ads() and generate_google_ads(), platform-reported
conversions and revenue are split evenly across campaigns using a simple
1/campaign_count share. Real Meta and Google data distributes conversions
unevenly across campaigns based on budget, audience size, and performance.
This simplification is acceptable for Stratum's portfolio purposes but means
the synthetic marketing data does not reflect the uneven distribution typical
of real accounts. Fix for Conduit: not applicable -- real platform data is
used directly.