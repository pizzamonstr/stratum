# Architecture

> Diagrams to be added after Checkpoint A is demonstrable.

## Overview

```
SOURCES             INGESTION               WAREHOUSE       TRANSFORM       SERVING
───────             ─────────               ─────────       ─────────       ───────
Shopify   ────────► load_to_bigquery.py ──► BigQuery    ──► dbt Core   ──► Looker
(synthetic CSV)     (on demand)             raw_shopify     (6am daily)     Studio
```

## Key Decisions

See [decisions.md](decisions.md).
