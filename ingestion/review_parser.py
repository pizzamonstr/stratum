"""
review_parser.py

Reads unparsed reviews from raw_enrichment.reviews_raw in BigQuery,
calls the LLM API to extract structured sentiment and topic fields,
and writes results to raw_enrichment.reviews_parsed.

Inputs:   BigQuery raw_enrichment.reviews_raw
Outputs:  BigQuery raw_enrichment.reviews_parsed
Schedule: On demand (initial Kaggle load), nightly 11pm (incremental)

TODO: Implement in Checkpoint B.
"""
