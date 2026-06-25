"""
generate_synthetic_data.py

Generates all synthetic Shopify and marketing source data for Stratum.
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

            # Apply or extend a stockout event.
            # Restock on the last day of a stockout so the next iteration
            # starts with available inventory and does not immediately
            # re-enter a stockout via the current_quantity == 0 path.
            was_out_of_stock = False
            if stockout_days_remaining > 0:
                was_out_of_stock = True
                current_quantity = 0
                stockout_days_remaining -= 1
                if stockout_days_remaining == 0:
                    current_quantity = velocity_starting[velocity]
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

            # Restock when days of cover is low and not currently stocked out.
            # Use a rolling 7-day average daily units sold to avoid over-
            # restocking on low-volume days.
            if not was_out_of_stock and current_quantity > 0:
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


# ── marketing helpers ─────────────────────────────────────────────────────────

def is_peak_month(order_date: date, seasonality: dict, threshold: float) -> bool:
    """Return True when the month's seasonality multiplier is at or above threshold.

    Parameters
    ----------
    order_date : date
        Date used to look up the month.
    seasonality : dict
        Month-to-multiplier mapping from config.
    threshold : float
        Minimum multiplier to classify as a peak month.

    Returns
    -------
    bool
        True if the month is considered peak season.
    """
    return seasonal_weight(order_date, seasonality) >= threshold


def build_daily_channel_totals(
    orders: list[dict],
) -> dict[str, dict[str, dict[str, float]]]:
    """Aggregate order count and net revenue by date and acquisition channel.

    Parameters
    ----------
    orders : list[dict]
        Generated Shopify order rows.

    Returns
    -------
    dict[str, dict[str, dict[str, float]]]
        date_str → channel → {order_count, net_revenue}.
    """
    daily_totals: dict[str, dict[str, dict[str, float]]] = {}

    for order in orders:
        date_str = order["created_at"][:10]
        channel = order["acquisition_channel"]
        daily_totals.setdefault(date_str, {})
        daily_totals[date_str].setdefault(
            channel, {"order_count": 0, "net_revenue": 0.0}
        )
        daily_totals[date_str][channel]["order_count"] += 1
        daily_totals[date_str][channel]["net_revenue"] += order["net_revenue"]

    return daily_totals


def random_in_range(range_cfg: dict) -> float:
    """Return a uniform random float between config min and max.

    Parameters
    ----------
    range_cfg : dict
        Mapping with 'min' and 'max' keys.

    Returns
    -------
    float
        Random value in the configured range.
    """
    return random.uniform(float(range_cfg["min"]), float(range_cfg["max"]))


def daily_spend_for_campaign(
    current_date: date,
    seasonality: dict,
    spend_cfg: dict,
    peak_threshold: float,
) -> float:
    """Compute seasonally-adjusted daily spend for one paid campaign.

    Parameters
    ----------
    current_date : date
        Calendar date for the spend row.
    seasonality : dict
        Month-to-multiplier mapping from config.
    spend_cfg : dict
        Source-specific marketing config with daily_spend_per_campaign.
    peak_threshold : float
        Seasonality multiplier at or above which peak spend applies.

    Returns
    -------
    float
        Daily spend amount in USD.
    """
    spend_key = (
        "peak"
        if is_peak_month(current_date, seasonality, peak_threshold)
        else "off_peak"
    )
    spend_range = spend_cfg["daily_spend_per_campaign"][spend_key]
    base_spend = random_in_range(spend_range)
    multiplier = seasonal_weight(current_date, seasonality)
    return round(base_spend * multiplier, 2)


def generate_meta_ads(
    cfg: dict,
    orders: list[dict],
) -> list[dict]:
    """Generate daily Meta ad insights at campaign and ad set grain.

    Parameters
    ----------
    cfg : dict
        Full configuration dictionary from synthetic_config.yml.
    orders : list[dict]
        Generated Shopify orders used to derive attribution overclaiming.

    Returns
    -------
    list[dict]
        One row per campaign per ad set per calendar day.
    """
    marketing_cfg = cfg["marketing"]
    meta_cfg = marketing_cfg["meta"]
    seasonality = cfg["seasonality"]
    peak_threshold = marketing_cfg["peak_seasonality_threshold"]
    daily_channel = build_daily_channel_totals(orders)
    all_dates = list(
        iter_date_range(cfg["date_range"]["start"], cfg["date_range"]["end"])
    )

    campaigns = []
    for idx in range(meta_cfg["prospecting_campaigns"]):
        campaigns.append({
            "campaign_id": str(uuid.uuid4()),
            "campaign_name": f"Prospecting - Outdoor Enthusiasts {idx + 1}",
            "campaign_objective": "OUTCOME_SALES",
            "audience_type": "prospecting",
        })
    for idx in range(meta_cfg["retargeting_campaigns"]):
        campaigns.append({
            "campaign_id": str(uuid.uuid4()),
            "campaign_name": f"Retargeting - Site Visitors {idx + 1}",
            "campaign_objective": "OUTCOME_SALES",
            "audience_type": "retargeting",
        })

    adset_lookup = {}
    for campaign in campaigns:
        audience = campaign["audience_type"]
        for adset_idx in range(meta_cfg["adsets_per_campaign"]):
            adset_id = str(uuid.uuid4())
            adset_lookup[campaign["campaign_id"]] = {
                "adset_id": adset_id,
                "adset_name": (
                    f"{campaign['campaign_name']} - Ad Set {adset_idx + 1}"
                ),
                "audience_type": audience,
            }

    rows: list[dict] = []
    campaign_count = len(campaigns)

    for current_date in all_dates:
        date_str = current_date.isoformat()
        paid_social = daily_channel.get(date_str, {}).get(
            "paid_social",
            {"order_count": 0, "net_revenue": 0.0},
        )
        actual_orders = int(paid_social["order_count"])
        actual_revenue = float(paid_social["net_revenue"])
        overclaim = random_in_range(
            meta_cfg["attribution_overclaim_multiplier"]
        )
        total_inflated_conversions = round(actual_orders * overclaim, 2)
        total_inflated_revenue = round(actual_revenue * overclaim, 2)

        for campaign in campaigns:
            adset = adset_lookup[campaign["campaign_id"]]
            audience = campaign["audience_type"]
            spend = daily_spend_for_campaign(
                current_date,
                seasonality,
                meta_cfg,
                peak_threshold,
            )
            cpm = random_in_range(meta_cfg["cpm"][audience])
            impressions = max(int((spend / cpm) * 1000), 1)
            ctr = random_in_range(meta_cfg["ctr"][audience])
            clicks = max(int(impressions * ctr), 0)
            reach_rate = random_in_range(meta_cfg["reach_rate"])
            reach = max(int(impressions * reach_rate), 1)
            frequency = round(impressions / reach, 2)

            share = 1.0 / campaign_count
            platform_conversions = round(
                total_inflated_conversions * share, 2
            )
            platform_revenue = round(total_inflated_revenue * share, 2)

            rows.append({
                "campaign_id": campaign["campaign_id"],
                "campaign_name": campaign["campaign_name"],
                "campaign_objective": campaign["campaign_objective"],
                "adset_id": adset["adset_id"],
                "adset_name": adset["adset_name"],
                "audience_type": audience,
                "date": date_str,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "reach": reach,
                "frequency": frequency,
                "platform_reported_conversions": platform_conversions,
                "platform_reported_revenue": platform_revenue,
            })

    return rows


def generate_google_ads(
    cfg: dict,
    orders: list[dict],
) -> list[dict]:
    """Generate daily Google Ads performance at campaign and ad group grain.

    Parameters
    ----------
    cfg : dict
        Full configuration dictionary from synthetic_config.yml.
    orders : list[dict]
        Generated Shopify orders used to derive attribution overclaiming.

    Returns
    -------
    list[dict]
        One row per campaign per ad group per calendar day.
    """
    marketing_cfg = cfg["marketing"]
    google_cfg = marketing_cfg["google"]
    seasonality = cfg["seasonality"]
    peak_threshold = marketing_cfg["peak_seasonality_threshold"]
    daily_channel = build_daily_channel_totals(orders)
    all_dates = list(
        iter_date_range(cfg["date_range"]["start"], cfg["date_range"]["end"])
    )

    campaigns = []
    for campaign_cfg in google_cfg["campaigns"]:
        campaigns.append({
            "campaign_id": str(uuid.uuid4()),
            "campaign_name": campaign_cfg["name"],
            "campaign_type": campaign_cfg["campaign_type"],
            "cpc_range": campaign_cfg["cpc"],
            "ctr_range": campaign_cfg["ctr"],
        })

    ad_group_lookup = {}
    for campaign in campaigns:
        ad_group_id = str(uuid.uuid4())
        ad_group_lookup[campaign["campaign_id"]] = {
            "ad_group_id": ad_group_id,
            "ad_group_name": f"{campaign['campaign_name']} - Ad Group 1",
        }

    rows: list[dict] = []
    campaign_count = len(campaigns)

    for current_date in all_dates:
        date_str = current_date.isoformat()
        paid_search = daily_channel.get(date_str, {}).get(
            "paid_search",
            {"order_count": 0, "net_revenue": 0.0},
        )
        actual_orders = int(paid_search["order_count"])
        actual_revenue = float(paid_search["net_revenue"])
        overclaim = random_in_range(
            google_cfg["attribution_overclaim_multiplier"]
        )
        total_inflated_conversions = round(actual_orders * overclaim, 2)
        total_inflated_revenue = round(actual_revenue * overclaim, 2)

        for campaign in campaigns:
            ad_group = ad_group_lookup[campaign["campaign_id"]]
            spend = daily_spend_for_campaign(
                current_date,
                seasonality,
                google_cfg,
                peak_threshold,
            )
            avg_cpc = random_in_range(campaign["cpc_range"])
            clicks = max(int(spend / avg_cpc), 1)
            ctr = random_in_range(campaign["ctr_range"])
            impressions = max(int(clicks / ctr), clicks)
            impression_share = round(
                random_in_range(google_cfg["impression_share"]), 4
            )
            lost_budget = round(
                random_in_range(
                    google_cfg["lost_impression_share_budget"]
                ),
                4,
            )
            share = 1.0 / campaign_count
            platform_conversions = round(
                total_inflated_conversions * share, 2
            )
            platform_revenue = round(total_inflated_revenue * share, 2)

            rows.append({
                "campaign_id": campaign["campaign_id"],
                "campaign_name": campaign["campaign_name"],
                "campaign_type": campaign["campaign_type"],
                "ad_group_id": ad_group["ad_group_id"],
                "ad_group_name": ad_group["ad_group_name"],
                "date": date_str,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "avg_cpc": round(avg_cpc, 2),
                "impression_share": impression_share,
                "lost_impression_share_budget": lost_budget,
                "platform_reported_conversions": platform_conversions,
                "platform_reported_revenue": platform_revenue,
            })

    return rows


def build_klaviyo_contact_pool(
    customers: list[dict],
    match_rate: float,
) -> list[dict]:
    """Build a Klaviyo contact pool mapped to Shopify customers where possible.

    Parameters
    ----------
    customers : list[dict]
        Generated Shopify customer rows.
    match_rate : float
        Fraction of contacts that map to a Shopify customer_id.

    Returns
    -------
    list[dict]
        Contact dicts with contact_id and optional customer_id.
    """
    matched_count = int(len(customers) * match_rate)
    matched_customers = random.sample(customers, matched_count)
    anonymous_count = max(int(len(customers) * (1 - match_rate)), 500)

    contacts = []
    for customer in matched_customers:
        contacts.append({
            "contact_id": customer["customer_id"],
            "customer_id": customer["customer_id"],
        })

    for _ in range(anonymous_count):
        contacts.append({
            "contact_id": str(uuid.uuid4()),
            "customer_id": None,
        })

    return contacts


def generate_klaviyo_events(
    cfg: dict,
    customers: list[dict],
    orders: list[dict],
) -> list[dict]:
    """Generate event-level Klaviyo email engagement data.

    Parameters
    ----------
    cfg : dict
        Full configuration dictionary from synthetic_config.yml.
    customers : list[dict]
        Generated Shopify customer rows.
    orders : list[dict]
        Generated Shopify orders for revenue overclaiming on conversions.

    Returns
    -------
    list[dict]
        One row per email event (sent, delivered, opened, etc.).
    """
    klaviyo_cfg = cfg["marketing"]["klaviyo"]
    start = date.fromisoformat(cfg["date_range"]["start"])
    end = date.fromisoformat(cfg["date_range"]["end"])

    email_orders = [
        order for order in orders
        if order["acquisition_channel"] == "email"
    ]
    email_revenue_by_date: dict[str, float] = {}
    for order in email_orders:
        date_str = order["created_at"][:10]
        email_revenue_by_date[date_str] = (
            email_revenue_by_date.get(date_str, 0.0) + order["net_revenue"]
        )

    contacts = build_klaviyo_contact_pool(
        customers,
        klaviyo_cfg["contact_customer_match_rate"],
    )
    flows = klaviyo_cfg["flows"]
    campaign_types = klaviyo_cfg["campaign_types"]

    rows: list[dict] = []
    email_counter = 0

    current_month = start.replace(day=1)
    while current_month <= end:
        month_end = (
            current_month.replace(day=28) + timedelta(days=4)
        ).replace(day=1) - timedelta(days=1)
        if month_end > end:
            month_end = end

        send_plan = [
            ("flow", klaviyo_cfg["monthly_sends"]["flow"]),
            ("campaign", klaviyo_cfg["monthly_sends"]["campaign"]),
        ]

        for email_type, send_count in send_plan:
            open_range = klaviyo_cfg["open_rate"][email_type]
            click_range = klaviyo_cfg["click_rate"][email_type]

            for _ in range(send_count):
                email_counter += 1
                contact = random.choice(contacts)
                email_id = str(uuid.uuid4())

                if email_type == "flow":
                    flow_name = random.choice(flows)
                    email_name = f"{flow_name.replace('_', ' ').title()} Email"
                else:
                    flow_name = None
                    campaign_label = random.choice(campaign_types)
                    email_name = (
                        f"{campaign_label.replace('_', ' ').title()} Blast"
                    )

                days_in_month = (month_end - current_month).days
                send_day = current_month + timedelta(
                    days=random.randint(0, max(days_in_month, 0))
                )
                send_hour = random.randint(8, 18)
                send_minute = random.randint(0, 59)
                occurred_at = datetime.combine(
                    send_day,
                    datetime.min.time(),
                ).replace(hour=send_hour, minute=send_minute)

                event_sequence = ["sent", "delivered"]
                open_rate = random_in_range(open_range)
                click_rate = random_in_range(click_range)
                opened = random.random() < open_rate
                clicked = opened and random.random() < click_rate
                converted = (
                    clicked
                    and random.random()
                    < random_in_range(
                        klaviyo_cfg["conversion_rate_on_click"]
                    )
                )
                unsubscribed = (
                    random.random() < random_in_range(
                        klaviyo_cfg["unsubscribe_rate"]
                    )
                )

                if opened:
                    event_sequence.append("opened")
                if clicked:
                    event_sequence.append("clicked")
                if converted:
                    event_sequence.append("converted")
                if unsubscribed:
                    event_sequence.append("unsubscribed")

                klaviyo_revenue = None
                if converted:
                    date_str = send_day.isoformat()
                    base_revenue = email_revenue_by_date.get(date_str, 0.0)
                    if base_revenue > 0:
                        overclaim = random_in_range(
                            klaviyo_cfg["revenue_overclaim_multiplier"]
                        )
                        klaviyo_revenue = round(
                            (base_revenue / max(send_count, 1)) * overclaim,
                            2,
                        )
                    else:
                        klaviyo_revenue = round(
                            random.uniform(25.0, 120.0)
                            * random_in_range(
                                klaviyo_cfg["revenue_overclaim_multiplier"]
                            ),
                            2,
                        )

                for offset_minutes, event_type in enumerate(event_sequence):
                    event_time = occurred_at + timedelta(
                        minutes=offset_minutes * random.randint(1, 45)
                    )
                    rows.append({
                        "event_id": str(uuid.uuid4()),
                        "email_id": email_id,
                        "email_name": email_name,
                        "email_type": email_type,
                        "flow_name": flow_name,
                        "contact_id": contact["contact_id"],
                        "event_type": event_type,
                        "occurred_at": event_time.isoformat(),
                        "klaviyo_reported_revenue": (
                            klaviyo_revenue
                            if event_type == "converted"
                            else None
                        ),
                    })

        if current_month.month == 12:
            current_month = current_month.replace(
                year=current_month.year + 1, month=1
            )
        else:
            current_month = current_month.replace(
                month=current_month.month + 1
            )

    return rows


def channel_to_ga4_source_medium(channel: str) -> tuple[str, str]:
    """Map Shopify acquisition channel to GA4 source and medium.

    Parameters
    ----------
    channel : str
        Shopify acquisition_channel value.

    Returns
    -------
    tuple[str, str]
        (acquisition_source, acquisition_medium) for GA4.
    """
    mapping = {
        "paid_social": ("facebook", "paid_social"),
        "paid_search": ("google", "cpc"),
        "organic": ("google", "organic"),
        "email": ("klaviyo", "email"),
        "direct": ("(direct)", "(none)"),
    }
    return mapping.get(channel, ("other", "referral"))


def generate_ga4_sessions(
    cfg: dict,
    orders: list[dict],
) -> list[dict]:
    """Generate session-level GA4 data aligned to Shopify channel mix.

    Parameters
    ----------
    cfg : dict
        Full configuration dictionary from synthetic_config.yml.
    orders : list[dict]
        Generated Shopify orders for channel distribution and conversions.

    Returns
    -------
    list[dict]
        One row per GA4 session.
    """
    ga4_cfg = cfg["marketing"]["ga4"]
    channels = cfg["channels"]
    start = date.fromisoformat(cfg["date_range"]["start"])
    end = date.fromisoformat(cfg["date_range"]["end"])
    date_span_days = (end - start).days

    target_total = ga4_cfg["target_total_sessions"]
    non_converting_pct = ga4_cfg["non_converting_session_pct"]
    converting_count = int(target_total * (1 - non_converting_pct))
    non_converting_count = target_total - converting_count

    order_pool = list(orders)
    if len(order_pool) > converting_count:
        converting_orders = random.sample(order_pool, converting_count)
    else:
        converting_orders = order_pool
        converting_count = len(converting_orders)
        non_converting_count = target_total - converting_count

    rows: list[dict] = []

    for order in converting_orders:
        channel = order["acquisition_channel"]
        source, medium = channel_to_ga4_source_medium(channel)
        order_date = date.fromisoformat(order["created_at"][:10])
        duration_cfg = ga4_cfg["session_duration_seconds"][channel]
        pages_cfg = ga4_cfg["pages_viewed"][channel]

        rows.append({
            "session_id": str(uuid.uuid4()),
            "ga4_client_id": str(uuid.uuid4()),
            "session_date": order_date.isoformat(),
            "acquisition_channel": channel,
            "acquisition_source": source,
            "acquisition_medium": medium,
            "landing_page": random.choice(ga4_cfg["landing_pages"]),
            "session_duration_seconds": random.randint(
                duration_cfg["min"], duration_cfg["max"]
            ),
            "pages_viewed": random.randint(
                pages_cfg["min"], pages_cfg["max"]
            ),
            "add_to_cart_events": random.randint(1, 3),
            "checkout_started": 1,
            "shopify_order_id": order["order_id"],
        })

    for _ in range(non_converting_count):
        channel = weighted_choice(channels)
        source, medium = channel_to_ga4_source_medium(channel)
        session_date = start + timedelta(
            days=random.randint(0, date_span_days)
        )
        duration_cfg = ga4_cfg["session_duration_seconds"][channel]
        pages_cfg = ga4_cfg["pages_viewed"][channel]
        add_to_cart = (
            1
            if random.random() < random_in_range(ga4_cfg["add_to_cart_rate"])
            else 0
        )
        checkout_started = (
            1
            if add_to_cart
            and random.random()
            < random_in_range(
                ga4_cfg["checkout_start_rate_on_add_to_cart"]
            )
            else 0
        )

        rows.append({
            "session_id": str(uuid.uuid4()),
            "ga4_client_id": str(uuid.uuid4()),
            "session_date": session_date.isoformat(),
            "acquisition_channel": channel,
            "acquisition_source": source,
            "acquisition_medium": medium,
            "landing_page": random.choice(ga4_cfg["landing_pages"]),
            "session_duration_seconds": random.randint(
                duration_cfg["min"], duration_cfg["max"]
            ),
            "pages_viewed": random.randint(
                pages_cfg["min"], pages_cfg["max"]
            ),
            "add_to_cart_events": add_to_cart,
            "checkout_started": checkout_started,
            "shopify_order_id": None,
        })

    return rows


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

    logger.info("Generating marketing sources ...")
    meta_ads = generate_meta_ads(cfg, orders)
    google_ads = generate_google_ads(cfg, orders)
    klaviyo_events = generate_klaviyo_events(cfg, customers, orders)
    ga4_sessions = generate_ga4_sessions(cfg, orders)

    logger.info("Writing CSVs ...")
    write_csv(customers, "shopify_customers", output_dir)
    write_csv(orders, "shopify_orders", output_dir)
    write_csv(line_items, "shopify_order_line_items", output_dir)
    write_csv(products, "shopify_products", output_dir)
    write_csv(inventory, "shopify_inventory", output_dir)
    write_csv(meta_ads, "meta_ad_insights", output_dir)
    write_csv(google_ads, "google_performance", output_dir)
    write_csv(klaviyo_events, "klaviyo_email_events", output_dir)
    write_csv(ga4_sessions, "ga4_sessions", output_dir)

    logger.info("Done.")
    logger.info("  orders     : %s", f"{len(orders):,}")
    logger.info("  line items : %s", f"{len(line_items):,}")
    logger.info("  customers  : %s", f"{len(customers):,}")
    logger.info(
        "  inventory  : %s rows (SKU × day)", f"{len(inventory):,}"
    )
    logger.info("  meta ads   : %s", f"{len(meta_ads):,}")
    logger.info("  google ads : %s", f"{len(google_ads):,}")
    logger.info("  klaviyo    : %s", f"{len(klaviyo_events):,}")
    logger.info("  ga4        : %s", f"{len(ga4_sessions):,}")

    if args.load:
        import subprocess
        logger.info("Loading to BigQuery ...")
        subprocess.run(
            ["python", "ingestion/load_to_bigquery.py"], check=True
        )


if __name__ == "__main__":
    main()
