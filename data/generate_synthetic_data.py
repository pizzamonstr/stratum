"""
generate_synthetic_data.py

Generates all synthetic Shopify source data for Stratum Checkpoint A.
All generation parameters are controlled by synthetic_config.yml.
Do not hard-code values that belong in config.

Inputs:   data/synthetic_config.yml
Outputs:  CSV files in the directory specified by config output.directory
Schedule: On demand
"""

import argparse
import csv
import logging
import random
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from faker import Faker

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

fake = Faker()


# ── config ────────────────────────────────────────────────────────────────────

def load_config(config_path: str) -> dict:
    """Load and return the YAML configuration file.

    Parameters
    ----------
    config_path : str
        Path to the synthetic_config.yml file.

    Returns
    -------
    dict
        Parsed configuration dictionary.

    Raises
    ------
    FileNotFoundError
        If no file exists at config_path.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(path) as config_file:
        return yaml.safe_load(config_file)


# ── sampling helpers ──────────────────────────────────────────────────────────

def weighted_choice(weights: dict) -> str:
    """Return a key sampled from a dict of key-to-weight pairs.

    Parameters
    ----------
    weights : dict
        Mapping of option label to sampling weight.

    Returns
    -------
    str
        The sampled key.
    """
    keys = list(weights.keys())
    weight_values = [weights[key] for key in keys]
    return random.choices(keys, weights=weight_values, k=1)[0]


def iter_date_range(start_str: str, end_str: str):
    """Yield every calendar date between start and end inclusive.

    Parameters
    ----------
    start_str : str
        Start date in YYYY-MM-DD format.
    end_str : str
        End date in YYYY-MM-DD format.

    Yields
    ------
    date
        Each calendar date in the range.
    """
    current = date.fromisoformat(start_str)
    end_date = date.fromisoformat(end_str)
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def seasonal_weight(order_date: date, multipliers: dict) -> float:
    """Return the seasonal demand multiplier for a given date.

    Parameters
    ----------
    order_date : date
        The date to look up.
    multipliers : dict
        Mapping of two-digit month string to float multiplier.

    Returns
    -------
    float
        The multiplier for that month. Defaults to 1.0 if month not found.
    """
    month_key = f"{order_date.month:02d}"
    return float(multipliers.get(month_key, 1.0))


def pick_order_date(
    start: date,
    end: date,
    seasonality: dict,
    earliest_allowed: date | None = None,
) -> date | None:
    """Pick a seasonally-weighted random order date via rejection sampling.

    Parameters
    ----------
    start : date
        Earliest possible order date.
    end : date
        Latest possible order date.
    seasonality : dict
        Month-to-multiplier mapping from config.
    earliest_allowed : date or None, optional
        Returned date must be strictly after this date.
        Used to ensure repeat orders follow prior orders.

    Returns
    -------
    date or None
        A valid sampled date, or None if max attempts are exhausted.
    """
    date_span_days = (end - start).days
    max_attempts = 100

    for _ in range(max_attempts):
        candidate = start + timedelta(days=random.randint(0, date_span_days))
        if earliest_allowed and candidate <= earliest_allowed:
            continue
        weight = seasonal_weight(candidate, seasonality)
        if random.random() < weight / 1.5:
            return candidate

    return None


# ── generators ────────────────────────────────────────────────────────────────

def generate_customers(cfg: dict) -> list[dict]:
    """Generate the synthetic customers table.

    Parameters
    ----------
    cfg : dict
        Full configuration dictionary from synthetic_config.yml.

    Returns
    -------
    list[dict]
        One dict per customer. total_orders and total_spent are
        initialised to zero and populated after order generation.
    """
    total = cfg["customers"]["total"]
    start = date.fromisoformat(cfg["date_range"]["start"])
    end = date.fromisoformat(cfg["date_range"]["end"])
    date_span_days = (end - start).days

    customers = []
    for _ in range(total):
        days_offset = random.randint(0, date_span_days)
        created_date = start + timedelta(days=days_offset)
        country = weighted_choice(cfg["geography"])

        customers.append({
            "customer_id": str(uuid.uuid4()),
            "email": fake.unique.email(),
            "created_at": datetime.combine(
                created_date, datetime.min.time()
            ).isoformat(),
            "city": fake.city(),
            "region": (
                fake.state_abbr() if country in ("US", "CA") else fake.city()
            ),
            "country": country,
            "total_orders": 0,
            "total_spent": 0.0,
        })

    return customers


def generate_line_items_for_order(
    order_id: str,
    sku_list: list[dict],
) -> list[dict]:
    """Generate 1-3 line items for a single order.

    Parameters
    ----------
    order_id : str
        The parent order ID to attach line items to.
    sku_list : list[dict]
        Full list of SKU configs from synthetic_config.yml.

    Returns
    -------
    list[dict]
        One dict per line item.
    """
    item_count = random.choices([1, 2, 3], weights=[0.60, 0.30, 0.10])[0]
    chosen_skus = random.sample(sku_list, min(item_count, len(sku_list)))

    line_items = []
    for sku_cfg in chosen_skus:
        quantity = random.choices([1, 2, 3], weights=[0.75, 0.20, 0.05])[0]
        unit_price = sku_cfg["price"]
        line_revenue = round(quantity * unit_price, 2)

        line_items.append({
            "line_item_id": str(uuid.uuid4()),
            "order_id": order_id,
            "sku": sku_cfg["sku"],
            "product_title": sku_cfg["title"],
            "product_category": sku_cfg["category"],
            "quantity": quantity,
            "unit_price": unit_price,
            "line_revenue": line_revenue,
        })

    return line_items


def generate_orders_and_line_items(
    customers: list[dict],
    cfg: dict,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Generate orders, line items, and updated customer totals.

    For each customer, determines a repeat order count based on the
    configured repeat purchase rate, picks seasonally-weighted order
    dates, and generates line items. Updates total_orders and
    total_spent on each customer record.

    Parameters
    ----------
    customers : list[dict]
        Customer rows as returned by generate_customers.
    cfg : dict
        Full configuration dictionary from synthetic_config.yml.

    Returns
    -------
    tuple[list[dict], list[dict], list[dict]]
        (orders, line_items, customers_with_updated_totals)
    """
    sku_list = cfg["skus"]
    seasonality = cfg["seasonality"]
    channels = cfg["channels"]
    discounts = cfg["discounts"]
    repeat_rate = cfg["customers"]["repeat_purchase_rate"]
    max_orders_per_customer = cfg["customers"]["max_orders_per_customer"]
    start = date.fromisoformat(cfg["date_range"]["start"])
    end = date.fromisoformat(cfg["date_range"]["end"])

    customer_lookup = {c["customer_id"]: c for c in customers}
    all_orders: list[dict] = []
    all_line_items: list[dict] = []

    for customer in customers:
        # Build up repeat order count via configured rate
        order_count = 1
        while (
            order_count < max_orders_per_customer
            and random.random() < repeat_rate
        ):
            order_count += 1

        prior_order_date = None

        for _ in range(order_count):
            order_date = pick_order_date(
                start=start,
                end=end,
                seasonality=seasonality,
                earliest_allowed=prior_order_date,
            )
            if order_date is None:
                # No valid date found -- skip remaining orders for this customer
                break

            order_id = str(uuid.uuid4())
            channel = weighted_choice(channels)

            has_discount = (
                random.random() < discounts["pct_orders_with_discount"]
            )
            discount_pct = (
                random.uniform(0.05, discounts["max_discount_pct"])
                if has_discount
                else 0.0
            )

            line_items = generate_line_items_for_order(order_id, sku_list)
            gross_revenue = sum(li["line_revenue"] for li in line_items)
            discount_amount = round(gross_revenue * discount_pct, 2)
            net_revenue = round(gross_revenue - discount_amount, 2)

            all_orders.append({
                "order_id": order_id,
                "customer_id": customer["customer_id"],
                "created_at": datetime.combine(
                    order_date, datetime.min.time()
                ).isoformat(),
                "financial_status": "paid",
                "gross_revenue": round(gross_revenue, 2),
                "discount_amount": discount_amount,
                "net_revenue": net_revenue,
                "acquisition_channel": channel,
                "shipping_country": customer["country"],
                "test_order": False,
            })
            all_line_items.extend(line_items)

            customer_lookup[customer["customer_id"]]["total_orders"] += 1
            customer_lookup[customer["customer_id"]]["total_spent"] += (
                net_revenue
            )
            prior_order_date = order_date

    for customer in customer_lookup.values():
        customer["total_spent"] = round(customer["total_spent"], 2)

    return all_orders, all_line_items, list(customer_lookup.values())


def generate_products(cfg: dict) -> list[dict]:
    """Generate the synthetic products table from the SKU catalogue.

    Parameters
    ----------
    cfg : dict
        Full configuration dictionary from synthetic_config.yml.

    Returns
    -------
    list[dict]
        One dict per SKU in the catalogue.
    """
    return [
        {
            "product_id": str(uuid.uuid4()),
            "sku": sku_cfg["sku"],
            "title": sku_cfg["title"],
            "category": sku_cfg["category"],
            "price": sku_cfg["price"],
            "cost_per_unit": sku_cfg["cost"],
        }
        for sku_cfg in cfg["skus"]
    ]


def build_daily_sales_index(
    orders: list[dict],
    line_items: list[dict],
) -> dict[str, dict[str, int]]:
    """Build a sku → date_str → units_sold index from order data.

    Parameters
    ----------
    orders : list[dict]
        Generated order rows.
    line_items : list[dict]
        Generated line item rows.

    Returns
    -------
    dict[str, dict[str, int]]
        Nested mapping of SKU to date string to units sold on that date.
    """
    order_date_by_id = {
        order["order_id"]: order["created_at"][:10]
        for order in orders
    }
    daily_sales: dict[str, dict[str, int]] = {}

    for line_item in line_items:
        sku = line_item["sku"]
        order_date_str = order_date_by_id.get(line_item["order_id"])
        if not order_date_str:
            continue
        daily_sales.setdefault(sku, {})
        daily_sales[sku][order_date_str] = (
            daily_sales[sku].get(order_date_str, 0) + line_item["quantity"]
        )

    return daily_sales


def generate_inventory(
    cfg: dict,
    orders: list[dict],
    line_items: list[dict],
) -> list[dict]:
    """Generate daily inventory positions for every SKU.

    Starts each SKU at the configured quantity, decrements by daily
    sales, triggers random stockout events, and restocks when days of
    cover falls below the configured threshold.

    Parameters
    ----------
    cfg : dict
        Full configuration dictionary from synthetic_config.yml.
    orders : list[dict]
        Generated order rows (used to build the daily sales index).
    line_items : list[dict]
        Generated line item rows.

    Returns
    -------
    list[dict]
        One dict per SKU per calendar date in the configured range.
    """
    inv_cfg = cfg["inventory"]
    seasonality = cfg["seasonality"]

    velocity_starting = {
        "high": inv_cfg["starting_units_high_velocity"],
        "medium": inv_cfg["starting_units_medium_velocity"],
        "low": inv_cfg["starting_units_low_velocity"],
    }
    velocity_stockout_prob = {
        "high": inv_cfg["stockout_probability_high"],
        "medium": inv_cfg["stockout_probability_medium"],
        "low": inv_cfg["stockout_probability_low"],
    }

    daily_sales = build_daily_sales_index(orders, line_items)
    all_dates = list(
        iter_date_range(cfg["date_range"]["start"], cfg["date_range"]["end"])
    )
    inventory_rows: list[dict] = []

    for sku_cfg in cfg["skus"]:
        sku = sku_cfg["sku"]
        velocity = sku_cfg["velocity"]
        current_quantity = velocity_starting[velocity]
        base_stockout_prob = velocity_stockout_prob[velocity]
        sku_daily_sales = daily_sales.get(sku, {})
        stockout_days_remaining = 0

        for current_date in all_dates:
            date_str = current_date.isoformat()
            units_sold = sku_daily_sales.get(date_str, 0)

            current_quantity = max(current_quantity - units_sold, 0)

            # Apply or extend a stockout event
            was_out_of_stock = False
            if stockout_days_remaining > 0:
                was_out_of_stock = True
                current_quantity = 0
                stockout_days_remaining -= 1
            elif current_quantity == 0 or (
                random.random()
                < base_stockout_prob
                * seasonal_weight(current_date, seasonality)
            ):
                was_out_of_stock = True
                current_quantity = 0
                stockout_days_remaining = random.randint(
                    1, inv_cfg["stockout_duration_max_days"]
                )

            # Restock when days of cover is low and not currently stocked out
            if not was_out_of_stock:
                avg_daily = max(units_sold, 1)
                days_of_cover = current_quantity // avg_daily
                if days_of_cover < inv_cfg["restock_trigger_days"]:
                    current_quantity += velocity_starting[velocity]

            inventory_rows.append({
                "sku": sku,
                "date": date_str,
                "inventory_quantity": current_quantity,
                "was_out_of_stock": was_out_of_stock,
            })

    return inventory_rows


# ── output ────────────────────────────────────────────────────────────────────

def write_csv(rows: list[dict], table_name: str, output_dir: str) -> None:
    """Write a list of row dicts to a CSV file.

    Parameters
    ----------
    rows : list[dict]
        Data rows to write. All dicts must share the same keys.
    table_name : str
        Used as the CSV filename stem (e.g. 'shopify_orders').
    output_dir : str
        Directory to write the file into.

    Raises
    ------
    ValueError
        If rows is empty.
    """
    if not rows:
        raise ValueError(f"No rows to write for table: {table_name}")

    output_path = Path(output_dir) / f"{table_name}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    logger.info(
        "%-35s %s rows → %s", table_name, f"{len(rows):,}", output_path
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Parse arguments, generate all synthetic tables, and write CSVs."""
    parser = argparse.ArgumentParser(
        description="Generate Stratum Checkpoint A synthetic data"
    )
    parser.add_argument(
        "--config",
        default="data/synthetic_config.yml",
        help="Path to synthetic_config.yml",
    )
    parser.add_argument(
        "--load",
        action="store_true",
        help="Call load_to_bigquery.py after generation",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    output_dir = cfg["output"]["directory"]

    logger.info("Stratum synthetic data generator")
    logger.info(
        "Range     : %s → %s",
        cfg["date_range"]["start"],
        cfg["date_range"]["end"],
    )
    logger.info("Customers : %s", f"{cfg['customers']['total']:,}")

    logger.info("Generating customers ...")
    customers = generate_customers(cfg)

    logger.info("Generating orders and line items ...")
    orders, line_items, customers = generate_orders_and_line_items(
        customers, cfg
    )

    logger.info("Generating products ...")
    products = generate_products(cfg)

    logger.info("Generating inventory ...")
    inventory = generate_inventory(cfg, orders, line_items)

    logger.info("Writing CSVs ...")
    write_csv(customers, "shopify_customers", output_dir)
    write_csv(orders, "shopify_orders", output_dir)
    write_csv(line_items, "shopify_order_line_items", output_dir)
    write_csv(products, "shopify_products", output_dir)
    write_csv(inventory, "shopify_inventory", output_dir)

    logger.info("Done.")
    logger.info("  orders     : %s", f"{len(orders):,}")
    logger.info("  line items : %s", f"{len(line_items):,}")
    logger.info("  customers  : %s", f"{len(customers):,}")
    logger.info(
        "  inventory  : %s rows (SKU × day)", f"{len(inventory):,}"
    )

    if args.load:
        import subprocess
        logger.info("Loading to BigQuery ...")
        subprocess.run(
            ["python", "ingestion/load_to_bigquery.py"], check=True
        )


if __name__ == "__main__":
    main()
