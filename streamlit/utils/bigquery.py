"""
bigquery.py

Shared BigQuery helpers for the Stratum Streamlit dashboard.
Reads credentials from st.secrets (Streamlit Cloud) or environment
variables (local development).
"""

import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account

# Load project-root .env when running locally.
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


def _get_config_value(key: str) -> str | None:
    """Read a config value from Streamlit secrets or environment.

    Parameters
    ----------
    key : str
        Configuration key name.

    Returns
    -------
    str or None
        Config value if found.
    """
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except (FileNotFoundError, RuntimeError):
        pass

    return os.getenv(key)


def _build_client() -> bigquery.Client:
    """Create a BigQuery client from secrets or environment credentials.

    Returns
    -------
    google.cloud.bigquery.Client
        Authenticated BigQuery client.

    Raises
    ------
    RuntimeError
        If no valid credentials are available.
    """
    project_id = _get_config_value("GCP_PROJECT_ID")

    try:
        if "gcp_service_account" in st.secrets:
            service_account_info = dict(st.secrets["gcp_service_account"])
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info
            )
            return bigquery.Client(
                credentials=credentials,
                project=project_id or service_account_info.get("project_id"),
            )
    except (FileNotFoundError, RuntimeError, KeyError, ValueError):
        pass

    credentials_path = _get_config_value("GOOGLE_APPLICATION_CREDENTIALS")
    if credentials_path:
        resolved_path = Path(credentials_path)
        if not resolved_path.is_absolute():
            resolved_path = (
                Path(__file__).resolve().parent.parent.parent / resolved_path
            )

        if resolved_path.exists():
            credentials = service_account.Credentials.from_service_account_file(
                str(resolved_path)
            )
            return bigquery.Client(
                credentials=credentials,
                project=project_id or credentials.project_id,
            )

    try:
        return bigquery.Client(project=project_id)
    except Exception as exc:
        raise RuntimeError(
            "BigQuery credentials not found. Set st.secrets "
            "(gcp_service_account or GOOGLE_APPLICATION_CREDENTIALS) for "
            "Streamlit Cloud, or GOOGLE_APPLICATION_CREDENTIALS and "
            "GCP_PROJECT_ID in your local .env file."
        ) from exc


@st.cache_resource
def get_bigquery_client() -> bigquery.Client:
    """Return a cached BigQuery client.

    Returns
    -------
    google.cloud.bigquery.Client
        Authenticated BigQuery client.

    Raises
    ------
    RuntimeError
        If credentials are missing or invalid.
    """
    try:
        return _build_client()
    except Exception as exc:
        raise RuntimeError(
            "Could not initialise BigQuery client. "
            "Check your Streamlit secrets or local .env configuration."
        ) from exc


def get_mart_dataset() -> str:
    """Return the BigQuery dataset that holds mart tables.

    Returns
    -------
    str
        Mart dataset name from secrets or environment.
    """
    dataset = _get_config_value("GCP_DATASET_MARTS")
    if dataset:
        return dataset

    try:
        if "GCP_DATASET_MARTS" in st.secrets:
            return str(st.secrets["GCP_DATASET_MARTS"])
    except (FileNotFoundError, RuntimeError):
        pass

    raise RuntimeError(
        "Mart dataset not configured. Set GCP_DATASET_MARTS in "
        "st.secrets or your local .env file."
    )


def mart_table_query(table_name: str) -> str:
    """Build a SELECT * query for a mart table.

    Parameters
    ----------
    table_name : str
        Mart table name without project or dataset qualifiers.

    Returns
    -------
    str
        SQL query string.
    """
    client = get_bigquery_client()
    dataset = get_mart_dataset()
    table_ref = f"`{client.project}.{dataset}.{table_name}`"
    return f"select * from {table_ref}"


@st.cache_data(ttl=3600)
def run_query(query: str) -> pd.DataFrame:
    """Run a SQL query and return results as a DataFrame.

    Parameters
    ----------
    query : str
        SQL query to execute.

    Returns
    -------
    pandas.DataFrame
        Query results.

    Raises
    ------
    RuntimeError
        If the query fails.
    """
    try:
        client = get_bigquery_client()
        query_job = client.query(query)
        return query_job.to_dataframe()
    except Exception as exc:
        st.error(f"BigQuery query failed: {exc}")
        raise RuntimeError(f"BigQuery query failed: {exc}") from exc
