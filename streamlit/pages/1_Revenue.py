"""
1_Revenue.py

Revenue Overview dashboard page.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.bigquery import mart_table_query, run_query

st.title("Revenue Overview")

new_vs_returning = run_query(mart_table_query("mart_new_vs_returning"))
revenue_summary = run_query(mart_table_query("mart_revenue_summary"))

new_vs_returning["month"] = pd.to_datetime(new_vs_returning["month"])

total_revenue = new_vs_returning["revenue"].sum()
total_orders = new_vs_returning["orders"].sum()
avg_order_value = (
    total_revenue / total_orders if total_orders > 0 else 0.0
)

metric_col_1, metric_col_2, metric_col_3 = st.columns(3)
metric_col_1.metric("Total Net Revenue", f"${total_revenue:,.2f}")
metric_col_2.metric("Total Orders", f"{total_orders:,}")
metric_col_3.metric("Avg Order Value", f"${avg_order_value:,.2f}")

monthly_revenue = (
    new_vs_returning.groupby("month", as_index=False)["revenue"]
    .sum()
    .sort_values("month")
)

st.subheader("Monthly Net Revenue Trend")
trend_fig = px.line(
    monthly_revenue,
    x="month",
    y="revenue",
    markers=True,
    labels={"month": "Month", "revenue": "Net Revenue (USD)"},
)
trend_fig.update_layout(hovermode="x unified")
st.plotly_chart(trend_fig, use_container_width=True)

st.subheader("New vs Returning Revenue")
stacked_data = new_vs_returning.pivot_table(
    index="month",
    columns="customer_type",
    values="revenue",
    aggfunc="sum",
    fill_value=0,
).reset_index()

customer_types = [
    column
    for column in ["new", "returning"]
    if column in stacked_data.columns
]

stacked_fig = px.bar(
    stacked_data,
    x="month",
    y=customer_types,
    labels={"month": "Month", "value": "Net Revenue (USD)"},
    title="Monthly Revenue by Customer Type",
)
stacked_fig.update_layout(barmode="stack")
st.plotly_chart(stacked_fig, use_container_width=True)

summary_has_breakdowns = {
    "product_category",
    "acquisition_channel",
    "revenue",
}.issubset(set(revenue_summary.columns))

if summary_has_breakdowns:
    category_data = (
        revenue_summary.groupby("product_category", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
    )
    channel_data = (
        revenue_summary.groupby("acquisition_channel", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
    )
else:
    st.info(
        "mart_revenue_summary is not yet populated. Showing category and "
        "channel breakdowns from mart_orders."
    )
    orders = run_query(mart_table_query("mart_orders"))

    category_data = (
        orders.groupby("product_category", as_index=False)["line_revenue"]
        .sum()
        .rename(columns={"line_revenue": "revenue"})
        .sort_values("revenue", ascending=False)
    )

    order_grain = orders.drop_duplicates(subset=["order_id"])
    channel_data = (
        order_grain.groupby("acquisition_channel", as_index=False)["net_revenue"]
        .sum()
        .rename(columns={"net_revenue": "revenue"})
        .sort_values("revenue", ascending=False)
    )

chart_col_1, chart_col_2 = st.columns(2)

with chart_col_1:
    st.subheader("Revenue by Product Category")
    category_fig = px.bar(
        category_data,
        x="product_category",
        y="revenue",
        labels={
            "product_category": "Category",
            "revenue": "Net Revenue (USD)",
        },
    )
    st.plotly_chart(category_fig, use_container_width=True)

with chart_col_2:
    st.subheader("Revenue by Acquisition Channel")
    channel_fig = px.bar(
        channel_data,
        x="acquisition_channel",
        y="revenue",
        labels={
            "acquisition_channel": "Channel",
            "revenue": "Net Revenue (USD)",
        },
    )
    st.plotly_chart(channel_fig, use_container_width=True)
