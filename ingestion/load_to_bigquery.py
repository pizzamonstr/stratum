"""
load_to_bigquery.py

Loads CSV files from data/sample_outputs/ into BigQuery raw schemas.
Also loads Kaggle enrichment datasets (reviews and support tickets) into
raw_enrichment. Uses python-dotenv to read GCP_PROJECT_ID and
GOOGLE_APPLICATION_CREDENTIALS from .env. Never reads credentials from code.

Inputs:   CSV files in data/sample_outputs/
          Kaggle CSVs in ~/Downloads/ (reviews and tickets)
          .env for GCP_PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS
Outputs:  BigQuery tables in raw_shopify, raw_marketing, raw_enrichment
Schedule: On demand (run after generate_synthetic_data.py)
"""

import argparse
import hashlib
import logging
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Validate required environment variables at startup -- fail fast
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
if not GCP_PROJECT_ID:
    raise ValueError(
        "GCP_PROJECT_ID not found in environment. Check your .env file."
    )

GCP_DATASET_RAW = os.getenv("GCP_DATASET_RAW", "raw_shopify")
GCP_DATASET_MARKETING = os.getenv("GCP_DATASET_MARKETING", "raw_marketing")
GCP_DATASET_ENRICHMENT = os.getenv("GCP_DATASET_ENRICHMENT", "raw_enrichment")
DATA_DIR = Path("data/sample_outputs")
DOWNLOADS_DIR = Path.home() / "Downloads"

REVIEWS_SOURCE_FILES = [
    "Datafiniti_Amazon_Consumer_Reviews_of_Amazon_Products.csv",
    "Datafiniti_Amazon_Consumer_Reviews_of_Amazon_Products_May19.csv",
    "1429_1.csv",
]
TICKETS_SOURCE_FILE = "customer_support_tickets.csv"

REVIEWS_COMMON_COLUMNS = [
    "id",
    "name",
    "brand",
    "categories",
    "reviews.id",
    "reviews.date",
    "reviews.rating",
    "reviews.text",
    "reviews.title",
    "reviews.doRecommend",
    "reviews.numHelpful",
    "reviews.username",
]

HARD_GOODS_KEYWORDS = [
    "Electronics",
    "Camera",
    "Computer",
    "Tablet",
    "Phone",
    "TV",
]
CONSUMABLES_KEYWORDS = [
    "Beauty",
    "Health",
    "Grocery",
    "Food",
    "Sports nutrition",
]

# Maps CSV stem name to (BigQuery table name, write disposition)
TABLE_CONFIG: dict[str, tuple[str, bigquery.WriteDisposition]] = {
    "shopify_customers": (
        "shopify_customers",
        bigquery.WriteDisposition.WRITE_TRUNCATE,
    ),
    "shopify_orders": (
        "shopify_orders",
        bigquery.WriteDisposition.WRITE_TRUNCATE,
    ),
    "shopify_order_line_items": (
        "shopify_order_line_items",
        bigquery.WriteDisposition.WRITE_TRUNCATE,
    ),
    "shopify_products": (
        "shopify_products",
        bigquery.WriteDisposition.WRITE_TRUNCATE,
    ),
    "shopify_inventory": (
        "shopify_inventory",
        bigquery.WriteDisposition.WRITE_TRUNCATE,
    ),
}

MARKETING_TABLE_CONFIG: dict[str, tuple[str, bigquery.WriteDisposition]] = {
    "meta_ad_insights": (
        "meta_ad_insights",
        bigquery.WriteDisposition.WRITE_TRUNCATE,
    ),
    "google_performance": (
        "google_performance",
        bigquery.WriteDisposition.WRITE_TRUNCATE,
    ),
    "klaviyo_email_events": (
        "klaviyo_email_events",
        bigquery.WriteDisposition.WRITE_TRUNCATE,
    ),
    "ga4_sessions": (
        "ga4_sessions",
        bigquery.WriteDisposition.WRITE_TRUNCATE,
    ),
}


def ensure_dataset_exists(
    client: bigquery.Client,
    dataset_id: str,
) -> None:
    """Create the BigQuery dataset if it does not already exist.

    Parameters
    ----------
    client : bigquery.Client
        Authenticated BigQuery client.
    dataset_id : str
        Dataset name (not the full reference).

    Raises
    ------
    google.cloud.exceptions.GoogleCloudError
        If the dataset cannot be created due to a permissions error.
    """
    dataset_ref = bigquery.Dataset(f"{GCP_PROJECT_ID}.{dataset_id}")
    dataset_ref.location = "US"
    try:
        client.create_dataset(dataset_ref, exists_ok=True)
    except Exception as exc:
        logger.error("Could not create dataset %s: %s", dataset_id, exc)
        raise
    logger.info("Dataset confirmed: %s.%s", GCP_PROJECT_ID, dataset_id)


def load_table_from_csv(
    client: bigquery.Client,
    csv_stem: str,
    dataset_id: str,
    table_config: dict[str, tuple[str, bigquery.WriteDisposition]],
) -> None:
    """Load a single CSV file into its corresponding BigQuery table.

    Parameters
    ----------
    client : bigquery.Client
        Authenticated BigQuery client.
    csv_stem : str
        CSV filename stem (e.g. 'shopify_orders'). Used to look up
        the table config and locate the file in DATA_DIR.
    dataset_id : str
        BigQuery dataset name (not the full reference).
    table_config : dict
        Mapping of CSV stem to (table name, write disposition).

    Raises
    ------
    KeyError
        If csv_stem is not a recognised key in table_config.
    FileNotFoundError
        If the CSV file does not exist in DATA_DIR.
    RuntimeError
        If the BigQuery load job completes with errors.
    """
    if csv_stem not in table_config:
        raise KeyError(
            f"Unknown table: '{csv_stem}'. "
            f"Valid options: {list(table_config.keys())}"
        )

    bq_table_name, write_disposition = table_config[csv_stem]
    csv_path = DATA_DIR / f"{csv_stem}.csv"

    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV not found: {csv_path}. "
            "Run generate_synthetic_data.py first."
        )

    table_ref = f"{GCP_PROJECT_ID}.{dataset_id}.{bq_table_name}"
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        autodetect=True,
        write_disposition=write_disposition,
    )

    try:
        with open(csv_path, "rb") as csv_file:
            load_job = client.load_table_from_file(
                csv_file, table_ref, job_config=job_config
            )
        load_job.result()  # block until the job completes
    except Exception as exc:
        logger.error("Load failed for %s: %s", table_ref, exc)
        raise

    loaded_table = client.get_table(table_ref)
    logger.info(
        "Loaded %-55s %s rows",
        table_ref,
        f"{loaded_table.num_rows:,}",
    )


def load_marketing_data(client: bigquery.Client) -> None:
    """Load all marketing CSVs into the raw_marketing BigQuery dataset.

    Parameters
    ----------
    client : bigquery.Client
        Authenticated BigQuery client.

    Raises
    ------
    google.cloud.exceptions.GoogleCloudError
        If dataset creation or any table load fails.
    """
    try:
        ensure_dataset_exists(client, GCP_DATASET_MARKETING)
    except Exception as exc:
        logger.error(
            "Could not prepare marketing dataset %s: %s",
            GCP_DATASET_MARKETING,
            exc,
        )
        raise

    for csv_stem in MARKETING_TABLE_CONFIG:
        try:
            load_table_from_csv(
                client,
                csv_stem,
                GCP_DATASET_MARKETING,
                MARKETING_TABLE_CONFIG,
            )
        except Exception as exc:
            logger.error("Marketing load failed for %s: %s", csv_stem, exc)
            raise

    logger.info("Marketing load complete.")


def map_product_category(text_value: str | float | None) -> str:
    """Map a free-text field to one of three product categories.

    Parameters
    ----------
    text_value : str, float, or None
        Categories string (reviews) or product name (tickets).

    Returns
    -------
    str
        One of 'hard_goods', 'consumables', or 'accessories'.
    """
    if text_value is None or (isinstance(text_value, float) and pd.isna(text_value)):
        return "accessories"

    text = str(text_value)
    for keyword in HARD_GOODS_KEYWORDS:
        if keyword in text:
            return "hard_goods"

    for keyword in CONSUMABLES_KEYWORDS:
        if keyword in text:
            return "consumables"

    return "accessories"


def load_dataframe_to_table(
    client: bigquery.Client,
    dataframe: pd.DataFrame,
    dataset_id: str,
    table_name: str,
    write_disposition: bigquery.WriteDisposition = (
        bigquery.WriteDisposition.WRITE_TRUNCATE
    ),
) -> int:
    """Load a pandas DataFrame into a BigQuery table.

    Parameters
    ----------
    client : bigquery.Client
        Authenticated BigQuery client.
    dataframe : pd.DataFrame
        Rows to load.
    dataset_id : str
        BigQuery dataset name (not the full reference).
    table_name : str
        BigQuery table name.
    write_disposition : bigquery.WriteDisposition, optional
        How to handle existing table data. Default is WRITE_TRUNCATE.

    Returns
    -------
    int
        Number of rows in the loaded table.

    Raises
    ------
    RuntimeError
        If the BigQuery load job completes with errors.
    """
    table_ref = f"{GCP_PROJECT_ID}.{dataset_id}.{table_name}"
    job_config = bigquery.LoadJobConfig(
        write_disposition=write_disposition,
        autodetect=True,
    )

    try:
        load_job = client.load_table_from_dataframe(
            dataframe,
            table_ref,
            job_config=job_config,
        )
        load_job.result()
    except Exception as exc:
        logger.error("Load failed for %s: %s", table_ref, exc)
        raise

    loaded_table = client.get_table(table_ref)
    logger.info(
        "Loaded %-55s %s rows",
        table_ref,
        f"{loaded_table.num_rows:,}",
    )
    return loaded_table.num_rows


def _make_review_id(product_id: str, review_id: str | float | None, review_body: str) -> str:
    """Build a stable review identifier from source fields.

    Datafiniti ``id`` is a product record ID with many reviews per product.
    Use ``reviews.id`` when present; otherwise derive from product id and
    review body hash.

    Parameters
    ----------
    product_id : str
        Product record ID from the source ``id`` column.
    review_id : str, float, or None
        Source ``reviews.id`` value when populated.
    review_body : str
        Review text used for fallback ID generation.

    Returns
    -------
    str
        Stable review identifier for deduplication and downstream parsing.
    """
    if review_id is not None and not (
        isinstance(review_id, float) and pd.isna(review_id)
    ):
        return str(review_id)

    body_hash = hashlib.md5(review_body.encode("utf-8")).hexdigest()[:16]
    return f"{product_id}_{body_hash}"


def _transform_reviews_file(
    csv_path: Path,
    source_filename: str,
) -> pd.DataFrame:
    """Read and normalise a single Datafiniti reviews CSV.

    Parameters
    ----------
    csv_path : Path
        Path to the source CSV file.
    source_filename : str
        Original filename stored in the source_file column.

    Returns
    -------
    pd.DataFrame
        Normalised review rows ready for deduplication and load.
    """
    available_columns = pd.read_csv(csv_path, nrows=0).columns.tolist()
    columns_to_read = [
        column
        for column in REVIEWS_COMMON_COLUMNS
        if column in available_columns
    ]

    reviews = pd.read_csv(csv_path, usecols=columns_to_read, low_memory=False)

    if "brand" not in reviews.columns:
        reviews["brand"] = None
    if "categories" not in reviews.columns:
        reviews["categories"] = None
    if "reviews.id" not in reviews.columns:
        reviews["reviews.id"] = None

    reviews = reviews.rename(
        columns={
            "name": "product_name",
            "reviews.date": "review_date",
            "reviews.rating": "star_rating",
            "reviews.text": "review_body",
            "reviews.title": "review_title",
            "reviews.doRecommend": "do_recommend",
            "reviews.numHelpful": "helpful_votes",
            "reviews.username": "reviewer_username",
        }
    )

    reviews["star_rating"] = pd.to_numeric(
        reviews["star_rating"],
        errors="coerce",
    )
    reviews["helpful_votes"] = pd.to_numeric(
        reviews["helpful_votes"],
        errors="coerce",
    ).astype("Int64")

    reviews = reviews[reviews["review_body"].notna()]
    reviews["review_id"] = reviews.apply(
        lambda row: _make_review_id(
            str(row["id"]),
            row["reviews.id"],
            str(row["review_body"]),
        ),
        axis=1,
    )
    reviews = reviews.drop(columns=["id", "reviews.id"])

    reviews["source_file"] = source_filename
    reviews["parsed_at"] = None
    reviews["parse_failed"] = None
    reviews["product_category"] = reviews["categories"].apply(
        map_product_category
    )

    return reviews


def load_reviews_data(client: bigquery.Client) -> None:
    """Load combined Datafiniti review CSVs into raw_enrichment.reviews_raw.

    Parameters
    ----------
    client : bigquery.Client
        Authenticated BigQuery client.

    Raises
    ------
    FileNotFoundError
        If any source CSV is missing from ~/Downloads/.
    google.cloud.exceptions.GoogleCloudError
        If dataset creation or the table load fails.
    """
    try:
        ensure_dataset_exists(client, GCP_DATASET_ENRICHMENT)
    except Exception as exc:
        logger.error(
            "Could not prepare enrichment dataset %s: %s",
            GCP_DATASET_ENRICHMENT,
            exc,
        )
        raise

    review_frames = []
    for filename in REVIEWS_SOURCE_FILES:
        csv_path = DOWNLOADS_DIR / filename
        if not csv_path.exists():
            raise FileNotFoundError(
                f"Reviews CSV not found: {csv_path}. "
                "Download the Datafiniti files to ~/Downloads/."
            )

        file_reviews = _transform_reviews_file(csv_path, filename)
        logger.info(
            "Read %s rows from %s (after dropping null review_body)",
            f"{len(file_reviews):,}",
            filename,
        )
        review_frames.append(file_reviews)

    combined_reviews = pd.concat(review_frames, ignore_index=True)
    rows_before_dedup = len(combined_reviews)

    combined_reviews = combined_reviews.drop_duplicates(
        subset=["review_id", "source_file"],
        keep="first",
    )
    rows_after_dedup = len(combined_reviews)

    logger.info(
        "Reviews deduplicated: %s -> %s rows",
        f"{rows_before_dedup:,}",
        f"{rows_after_dedup:,}",
    )

    try:
        load_dataframe_to_table(
            client,
            combined_reviews,
            GCP_DATASET_ENRICHMENT,
            "reviews_raw",
        )
    except Exception as exc:
        logger.error("Reviews load failed: %s", exc)
        raise

    logger.info("Reviews load complete.")


def load_tickets_data(client: bigquery.Client) -> None:
    """Load customer support tickets into raw_enrichment.tickets_raw.

    Parameters
    ----------
    client : bigquery.Client
        Authenticated BigQuery client.

    Raises
    ------
    FileNotFoundError
        If the tickets CSV is missing from ~/Downloads/.
    google.cloud.exceptions.GoogleCloudError
        If dataset creation or the table load fails.
    """
    try:
        ensure_dataset_exists(client, GCP_DATASET_ENRICHMENT)
    except Exception as exc:
        logger.error(
            "Could not prepare enrichment dataset %s: %s",
            GCP_DATASET_ENRICHMENT,
            exc,
        )
        raise

    csv_path = DOWNLOADS_DIR / TICKETS_SOURCE_FILE
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Tickets CSV not found: {csv_path}. "
            "Download customer_support_tickets.csv to ~/Downloads/."
        )

    tickets = pd.read_csv(csv_path)
    tickets = tickets.rename(
        columns={
            "Ticket ID": "ticket_id",
            "Customer Name": "customer_name",
            "Customer Email": "customer_email",
            "Customer Age": "customer_age",
            "Customer Gender": "customer_gender",
            "Product Purchased": "product_name",
            "Date of Purchase": "purchase_date",
            "Ticket Type": "ticket_type",
            "Ticket Subject": "ticket_subject",
            "Ticket Description": "ticket_description",
            "Ticket Status": "ticket_status",
            "Resolution": "resolution",
            "Ticket Priority": "ticket_priority",
            "Ticket Channel": "ticket_channel",
            "First Response Time": "first_response_time",
            "Time to Resolution": "time_to_resolution",
            "Customer Satisfaction Rating": "customer_satisfaction_rating",
        }
    )

    tickets["created_at"] = None
    tickets["resolved_at"] = None
    tickets["parsed_at"] = None
    tickets["parse_failed"] = None
    tickets["product_category"] = tickets["product_name"].apply(
        map_product_category
    )

    tickets = tickets[tickets["ticket_description"].notna()]
    logger.info("Read %s ticket rows (after dropping null descriptions)", f"{len(tickets):,}")

    try:
        load_dataframe_to_table(
            client,
            tickets,
            GCP_DATASET_ENRICHMENT,
            "tickets_raw",
        )
    except Exception as exc:
        logger.error("Tickets load failed: %s", exc)
        raise

    logger.info("Tickets load complete.")


def main() -> None:
    """Parse arguments and load all or one table to BigQuery."""
    parser = argparse.ArgumentParser(
        description="Load Stratum synthetic CSVs to BigQuery"
    )
    parser.add_argument(
        "--table",
        help=(
            "Load a single table by CSV stem name. "
            "Loads all tables if omitted."
        ),
    )
    args = parser.parse_args()

    try:
        client = bigquery.Client(project=GCP_PROJECT_ID)
    except Exception as exc:
        logger.error("Could not create BigQuery client: %s", exc)
        raise

    ensure_dataset_exists(client, GCP_DATASET_RAW)

    tables_to_load = (
        [args.table] if args.table else list(TABLE_CONFIG.keys())
    )
    for csv_stem in tables_to_load:
        load_table_from_csv(
            client,
            csv_stem,
            GCP_DATASET_RAW,
            TABLE_CONFIG,
        )

    load_marketing_data(client)
    load_reviews_data(client)
    load_tickets_data(client)

    logger.info("Load complete.")


if __name__ == "__main__":
    main()
