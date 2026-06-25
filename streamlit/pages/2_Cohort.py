"""
2_Cohort.py

Cohort Analysis dashboard page.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.bigquery import mart_table_query, run_query

st.title("Cohort Analysis")

cohort_data = run_query(mart_table_query("mart_cohort_analysis"))
customers = run_query(mart_table_query("mart_customers"))

total_customers = len(customers)
total_orders = customers["total_orders"].sum()
total_revenue = customers["total_revenue"].sum()
avg_order_value = (
    total_revenue / total_orders if total_orders > 0 else 0.0
)
returning_customers = (customers["total_orders"] > 1).sum()
pct_returning = (
    (returning_customers / total_customers) * 100
    if total_customers > 0
    else 0.0
)

metric_col_1, metric_col_2, metric_col_3 = st.columns(3)
metric_col_1.metric("Total Customers", f"{total_customers:,}")
metric_col_2.metric("Avg Order Value", f"${avg_order_value:,.2f}")
metric_col_3.metric("Returning Customers", f"{pct_returning:.1f}%")

st.subheader("Cohort Retention Heatmap")
cohort_data["cohort_month"] = pd.to_datetime(cohort_data["cohort_month"])

heatmap_pivot = cohort_data.pivot_table(
    index="cohort_month",
    columns="months_since_first_purchase",
    values="customers_active",
    aggfunc="sum",
    fill_value=0,
)

heatmap_pivot = heatmap_pivot.sort_index()
heatmap_pivot.index = heatmap_pivot.index.strftime("%Y-%m")

heatmap_fig = px.imshow(
    heatmap_pivot,
    labels={
        "x": "Months Since First Purchase",
        "y": "Cohort Month",
        "color": "Active Customers",
    },
    aspect="auto",
    color_continuous_scale="Blues",
)
heatmap_fig.update_xaxes(side="top")
st.plotly_chart(heatmap_fig, use_container_width=True)

st.subheader("Customer Segment Breakdown")
segment_counts = (
    customers["customer_segment"]
    .value_counts()
    .reset_index()
)
segment_counts.columns = ["customer_segment", "customers"]

segment_fig = px.pie(
    segment_counts,
    names="customer_segment",
    values="customers",
    title="Customers by Segment",
    hole=0.35,
)
st.plotly_chart(segment_fig, use_container_width=True)
