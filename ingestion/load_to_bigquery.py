"""
load_to_bigquery.py

Loads CSV files from data/sample_outputs/ into BigQuery raw schemas.
Uses python-dotenv to read GCP_PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS
from .env. Never reads credentials from code.

Inputs:   CSV files in data/sample_outputs/
          .env for GCP_PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS
Outputs:  BigQuery tables in the dataset named by GCP_DATASET_RAW
Schedule: On demand (run after generate_synthetic_data.py)
"""

import argparse
import logging
import os
import sys
from pathlib import Path

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
DATA_DIR = Path("data/sample_outputs")

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
) -> None:
    """Load a single CSV file into its corresponding BigQuery table.

    Parameters
    ----------
    client : bigquery.Client
        Authenticated BigQuery client.
    csv_stem : str
        CSV filename stem (e.g. 'shopify_orders'). Used to look up
        the table config and locate the file in DATA_DIR.

    Raises
    ------
    KeyError
        If csv_stem is not a recognised key in TABLE_CONFIG.
    FileNotFoundError
        If the CSV file does not exist in DATA_DIR.
    RuntimeError
        If the BigQuery load job completes with errors.
    """
    if csv_stem not in TABLE_CONFIG:
        raise KeyError(
            f"Unknown table: '{csv_stem}'. "
            f"Valid options: {list(TABLE_CONFIG.keys())}"
        )

    bq_table_name, write_disposition = TABLE_CONFIG[csv_stem]
    csv_path = DATA_DIR / f"{csv_stem}.csv"

    if not csv_path.exists():
        raise FileNotFoundError(
            f"CSV not found: {csv_path}. "
            "Run generate_synthetic_data.py first."
        )

    table_ref = f"{GCP_PROJECT_ID}.{GCP_DATASET_RAW}.{bq_table_name}"
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
        load_table_from_csv(client, csv_stem)

    logger.info("Load complete.")


if __name__ == "__main__":
    main()
