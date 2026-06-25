"""
3_Marketing.py

Marketing Attribution dashboard page.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.bigquery import get_mart_dataset, mart_table_query, run_query

st.title("Marketing Attribution")

PAID_CHANNELS = ["paid_social", "paid_search"]


def staging_table_query(table_name: str) -> str:
    """Build a SELECT * query for a staging view in the dbt staging schema."""
    staging_dataset = f"{get_mart_dataset()}_staging"
    table_ref = f"`{staging_dataset}.{table_name}`"
    return f"select * from {table_ref}"


def _month_start(series: pd.Series) -> pd.Series:
    """Normalize a date column to the first day of each calendar month."""
    return pd.to_datetime(series).dt.to_period("M").dt.to_timestamp()


def _most_recent_full_month_roas(blended_roas: pd.DataFrame) -> float | None:
    """Return blended ROAS for the latest complete calendar month."""
    current_month_start = pd.Timestamp.today().normalize().replace(day=1)
    full_months = blended_roas[blended_roas["month"] < current_month_start]

    if full_months.empty:
        return None

    latest_row = full_months.sort_values("month").iloc[-1]
    return float(latest_row["blended_roas"])


blended_roas = run_query(mart_table_query("mart_blended_roas"))
attribution = run_query(mart_table_query("mart_attribution"))

if blended_roas.empty:
    st.warning("mart_blended_roas has no data yet. KPIs and ROAS charts are unavailable.")
if attribution.empty:
    st.warning("mart_attribution has no data yet. Channel charts are unavailable.")

if not blended_roas.empty:
    blended_roas["month"] = _month_start(blended_roas["month"])

if not attribution.empty:
    attribution["month"] = _month_start(attribution["date"])

latest_roas = (
    _most_recent_full_month_roas(blended_roas)
    if not blended_roas.empty
    else None
)
total_paid_spend = (
    blended_roas["total_paid_spend"].sum()
    if not blended_roas.empty
    else 0.0
)
paid_channel_revenue = (
    attribution.loc[
        attribution["acquisition_channel"].isin(PAID_CHANNELS),
        "shopify_revenue",
    ].sum()
    if not attribution.empty
    else 0.0
)

metric_col_1, metric_col_2, metric_col_3 = st.columns(3)
metric_col_1.metric(
    "Blended ROAS (Latest Full Month)",
    f"{latest_roas:.2f}x" if latest_roas is not None else "N/A",
)
metric_col_2.metric("Total Paid Spend", f"${total_paid_spend:,.2f}")
metric_col_3.metric("Paid Channel Revenue", f"${paid_channel_revenue:,.2f}")

st.subheader("Monthly Blended ROAS")
if blended_roas.empty:
    st.warning("No blended ROAS data available.")
else:
    roas_trend = blended_roas.sort_values("month")
    roas_fig = px.line(
        roas_trend,
        x="month",
        y="blended_roas",
        markers=True,
        title="Monthly Blended ROAS",
        labels={
            "month": "Month",
            "blended_roas": "Blended ROAS",
        },
    )
    roas_fig.add_hline(
        y=1.0,
        line_dash="dash",
        line_color="gray",
        annotation_text="Break-even (1.0x)",
    )
    roas_fig.update_layout(hovermode="x unified")
    st.plotly_chart(roas_fig, use_container_width=True)

st.subheader("Monthly Revenue by Acquisition Channel")
if attribution.empty:
    st.warning("No attribution data available.")
else:
    monthly_channel_revenue = (
        attribution.groupby(["month", "acquisition_channel"], as_index=False)[
            "shopify_revenue"
        ]
        .sum()
        .sort_values("month")
    )
    channel_fig = px.bar(
        monthly_channel_revenue,
        x="month",
        y="shopify_revenue",
        color="acquisition_channel",
        title="Monthly Revenue by Acquisition Channel",
        labels={
            "month": "Month",
            "shopify_revenue": "Shopify Revenue (USD)",
            "acquisition_channel": "Channel",
        },
    )
    channel_fig.update_layout(barmode="stack", hovermode="x unified")
    st.plotly_chart(channel_fig, use_container_width=True)

st.subheader("Monthly Paid Spend by Platform")
if blended_roas.empty:
    st.warning("No paid spend data available.")
else:
    spend_by_platform = blended_roas.melt(
        id_vars=["month"],
        value_vars=["meta_spend", "google_spend"],
        var_name="platform",
        value_name="spend",
    )
    spend_by_platform["platform"] = spend_by_platform["platform"].map(
        {
            "meta_spend": "Meta",
            "google_spend": "Google",
        }
    )
    spend_fig = px.line(
        spend_by_platform.sort_values("month"),
        x="month",
        y="spend",
        color="platform",
        markers=True,
        title="Monthly Paid Spend by Platform",
        labels={"month": "Month", "spend": "Spend (USD)", "platform": "Platform"},
    )
    spend_fig.update_layout(hovermode="x unified")
    st.plotly_chart(spend_fig, use_container_width=True)

st.subheader("Paid Spend vs Shopify Revenue")
if blended_roas.empty or attribution.empty:
    st.warning("Paid spend vs revenue comparison requires both mart tables.")
else:
    paid_monthly_revenue = (
        attribution.loc[attribution["acquisition_channel"].isin(PAID_CHANNELS)]
        .groupby("month", as_index=False)["shopify_revenue"]
        .sum()
        .rename(columns={"shopify_revenue": "paid_shopify_revenue"})
    )
    spend_vs_revenue = blended_roas[
        ["month", "total_paid_spend"]
    ].merge(paid_monthly_revenue, on="month", how="left")
    spend_vs_revenue["paid_shopify_revenue"] = spend_vs_revenue[
        "paid_shopify_revenue"
    ].fillna(0)

    spend_vs_revenue_long = spend_vs_revenue.melt(
        id_vars=["month"],
        value_vars=["total_paid_spend", "paid_shopify_revenue"],
        var_name="metric",
        value_name="amount",
    )
    spend_vs_revenue_long["metric"] = spend_vs_revenue_long["metric"].map(
        {
            "total_paid_spend": "Paid Spend",
            "paid_shopify_revenue": "Shopify Revenue (Paid Channels)",
        }
    )
    spend_vs_revenue_fig = px.line(
        spend_vs_revenue_long.sort_values("month"),
        x="month",
        y="amount",
        color="metric",
        markers=True,
        title="Paid Spend vs Shopify Revenue",
        labels={"month": "Month", "amount": "Amount (USD)", "metric": "Metric"},
    )
    spend_vs_revenue_fig.update_layout(hovermode="x unified")
    st.plotly_chart(spend_vs_revenue_fig, use_container_width=True)

st.subheader("New vs Returning Revenue by Channel")
if attribution.empty:
    st.warning("No attribution data available for customer-type breakdown.")
else:
    paid_attribution = attribution[
        attribution["acquisition_channel"].isin(PAID_CHANNELS)
    ]
    if paid_attribution.empty:
        st.warning("No paid channel attribution data available.")
    else:
        monthly_customer_type = (
            paid_attribution.groupby(["month", "acquisition_channel"], as_index=False)[
                ["new_customer_revenue", "returning_customer_revenue"]
            ]
            .sum()
            .sort_values("month")
        )
        customer_type_long = monthly_customer_type.melt(
            id_vars=["month", "acquisition_channel"],
            value_vars=["new_customer_revenue", "returning_customer_revenue"],
            var_name="customer_type",
            value_name="revenue",
        )
        customer_type_long["customer_type"] = customer_type_long["customer_type"].map(
            {
                "new_customer_revenue": "New",
                "returning_customer_revenue": "Returning",
            }
        )
        customer_type_long["acquisition_channel"] = customer_type_long[
            "acquisition_channel"
        ].map(
            {
                "paid_social": "Paid Social",
                "paid_search": "Paid Search",
            }
        )
        customer_type_fig = px.bar(
            customer_type_long,
            x="month",
            y="revenue",
            color="customer_type",
            facet_row="acquisition_channel",
            barmode="group",
            title="New vs Returning Revenue by Channel",
            labels={
                "month": "Month",
                "revenue": "Revenue (USD)",
                "customer_type": "Customer Type",
                "acquisition_channel": "Channel",
            },
        )
        customer_type_fig.update_layout(hovermode="x unified")
        st.plotly_chart(customer_type_fig, use_container_width=True)

st.subheader("Platform-Reported vs Actual Revenue (Attribution Gap)")
meta_insights = run_query(staging_table_query("stg_meta__ad_insights"))
google_performance = run_query(staging_table_query("stg_google__performance"))

if meta_insights.empty and google_performance.empty:
    st.warning("Staging ad platform tables have no data yet.")
elif attribution.empty:
    st.warning("mart_attribution is required to compare against Shopify actuals.")
else:
    meta_insights["month"] = _month_start(meta_insights["date"])
    google_performance["month"] = _month_start(google_performance["date"])

    meta_reported_monthly = (
        meta_insights.groupby("month", as_index=False)["meta_reported_revenue"]
        .sum()
        .rename(columns={"meta_reported_revenue": "revenue"})
    )
    meta_reported_monthly["source"] = "Meta Reported"

    google_reported_monthly = (
        google_performance.groupby("month", as_index=False)["google_reported_revenue"]
        .sum()
        .rename(columns={"google_reported_revenue": "revenue"})
    )
    google_reported_monthly["source"] = "Google Reported"

    shopify_actual_monthly = (
        attribution.loc[attribution["acquisition_channel"].isin(PAID_CHANNELS)]
        .groupby("month", as_index=False)["shopify_revenue"]
        .sum()
        .rename(columns={"shopify_revenue": "revenue"})
    )
    shopify_actual_monthly["source"] = "Shopify Actual (Paid)"

    gap_comparison = pd.concat(
        [
            meta_reported_monthly,
            google_reported_monthly,
            shopify_actual_monthly,
        ],
        ignore_index=True,
    ).sort_values("month")

    if gap_comparison.empty:
        st.warning("No monthly revenue available for attribution gap comparison.")
    else:
        gap_fig = px.bar(
            gap_comparison,
            x="month",
            y="revenue",
            color="source",
            barmode="group",
            title="Platform-Reported vs Actual Revenue (Attribution Gap)",
            labels={
                "month": "Month",
                "revenue": "Revenue (USD)",
                "source": "Source",
            },
        )
        gap_fig.update_layout(hovermode="x unified")
        st.plotly_chart(gap_fig, use_container_width=True)

st.caption(
    "Platform-reported revenue includes view-through and cross-device attribution "
    "that inflates results relative to Shopify last-touch revenue. Shopify figures "
    "are the agreed source of truth for marketing reporting."
)
