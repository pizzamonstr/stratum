# Data Dictionary

Full column definitions for all mart models live in the YAML files
alongside each model in dbt_project/models/marts/.
This file provides a human-readable summary for quick reference.

## mart_orders

| Column | Type | Description |
|---|---|---|
| line_item_id | STRING | Primary key. One row per order line. |
| order_id | STRING | Shopify order ID. |
| customer_id | STRING | Shopify customer ID. |
| ordered_at | TIMESTAMP | Order creation timestamp. |
| net_revenue | FLOAT64 | gross_revenue minus discount_amount. Single agreed definition. |
| customer_type | STRING | 'new' on first order; 'returning' thereafter. |
| acquisition_channel | STRING | Last-touch channel from the order record. |

## mart_customers

| Column | Type | Description |
|---|---|---|
| customer_id | STRING | Primary key. |
| total_orders | INT64 | Lifetime distinct order count. |
| total_revenue | FLOAT64 | Lifetime net revenue, in USD. |
| avg_order_value | FLOAT64 | total_revenue ÷ total_orders. |
| customer_segment | STRING | 'one_time', 'occasional', or 'loyal'. |
| favourite_category | STRING | Category with highest lifetime line_revenue. |

## mart_inventory

| Column | Type | Description |
|---|---|---|
| sku | STRING | Product SKU. Composite key with inventory_date. |
| inventory_date | DATE | Calendar date. |
| was_out_of_stock | BOOL | True if stock hit zero on this day. |
| low_stock_flag | BOOL | True if quantity < low_stock_threshold (default 30). |
| days_of_stock_remaining | FLOAT64 | inventory_quantity ÷ avg_daily_sales_rate_30d. |
