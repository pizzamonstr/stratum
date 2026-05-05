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
