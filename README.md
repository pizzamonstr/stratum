# Stratum

Production-grade analytics pipeline for outdoor DTC e-commerce.
Synthetic data → BigQuery → dbt → Looker Studio.

Built as a portfolio project demonstrating end-to-end analytics engineering
across a realistic outdoor brand stack. All data is synthetic or from public
Kaggle datasets. No real brand data is included.

---

## Stack

| Layer          | Tool                        |
|----------------|-----------------------------|
| Warehouse      | BigQuery (free tier)        |
| Transformation | dbt Core                    |
| AI enrichment  | Python + Anthropic / OpenAI |
| Orchestration  | GitHub Actions              |
| Serving        | Looker Studio               |
| Synthetic data | Python + Faker              |

---

## Project Structure

```
stratum/
├── data/                       synthetic data generation + config
├── ingestion/                  BigQuery loaders and LLM parsers
├── dbt_project/                staging models, mart models, tests, macros
├── dashboards/screenshots/     Looker Studio exports (synthetic data only)
└── docs/                       architecture, data dictionary, decisions, limitations
```

---

## Build Checkpoints

| Checkpoint | Scope | Status |
|---|---|---|
| A | Pipeline spine: Shopify → dbt → dashboards | 🔲 In progress |
| B | Marketing attribution + LLM enrichment | 🔲 Not started |
| C | AI visibility layer + docs + polish | 🔲 Not started |

---

## Quickstart (Checkpoint A)

```bash
# 1. Clone and configure
git clone https://github.com/pizzamonstr/stratum.git
cd stratum
cp .env.example .env            # fill in GCP_PROJECT_ID and credentials path

# 2. Install dependencies
pip install -r requirements.txt
pip install dbt-bigquery

# 3. Generate synthetic Shopify data
python data/generate_synthetic_data.py

# 4. Load to BigQuery
python ingestion/load_to_bigquery.py

# 5. Run dbt
cd dbt_project
cp profiles.yml.example profiles.yml    # fill in your GCP project ID
dbt deps
dbt build
```

---

## Docs

- [Architecture](docs/architecture.md)
- [Data Dictionary](docs/data_dictionary.md)
- [Decisions](docs/decisions.md)
- [Limitations](docs/limitations.md)

---

*Version 4 — May 2026*
