-- assert_revenue_positive.sql
-- net_revenue must be >= 0 for all non-refund order line items.
-- A negative value indicates a data issue in the Shopify source
-- or a missing refund flag in the staging model.

select
    line_item_id,
    order_id,
    net_revenue,
    financial_status

from {{ ref('mart_orders') }}
where net_revenue < 0
  and financial_status not in ('refunded', 'partially_refunded')
