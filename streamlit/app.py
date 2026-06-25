"""
app.py

Stratum Analytics dashboard entry point.
Use the sidebar to navigate between dashboard pages.
"""

import streamlit as st

st.set_page_config(
    page_title="Stratum Analytics",
    page_icon="📊",
    layout="wide",
)

st.title("Stratum Analytics")
st.markdown(
    """
**Stratum** is a portfolio analytics pipeline for a generic DTC outdoor
e-commerce brand. It transforms synthetic Shopify transactional data through
dbt mart models in BigQuery into executive-ready metrics on revenue, cohort
retention, and customer behaviour.

Use the **sidebar** to navigate between dashboard pages:

- **Revenue** — net revenue trends, new vs returning split, category and
  channel breakdowns
- **Cohort** — retention heatmap and customer segment distribution
- **Marketing**, **Product Health**, and **AI Visibility** — coming in
  Checkpoint B/C
"""
)
