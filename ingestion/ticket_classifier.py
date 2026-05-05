"""
ticket_classifier.py

Reads unclassified support tickets from raw_enrichment.tickets_raw
in BigQuery, calls the LLM API to classify them, and writes results
to raw_enrichment.tickets_classified.

Inputs:   BigQuery raw_enrichment.tickets_raw
Outputs:  BigQuery raw_enrichment.tickets_classified
Schedule: On demand (initial Kaggle load), nightly 11pm (incremental)

TODO: Implement in Checkpoint B.
"""
