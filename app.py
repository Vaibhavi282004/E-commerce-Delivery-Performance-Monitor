
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
SAMPLE = ROOT / "data" / "raw_sample"
REPORTS = ROOT / "reports"

st.set_page_config(
    page_title="Olist | Analytics Studio",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}
.stApp {
    background: #0b1120;
    color: #edf2ff;
}
[data-testid="stSidebar"] {
    background: #111a2e;
    border-right: 1px solid #26334b;
}
[data-testid="stSidebar"] * {
    color: #dce6fa;
}
.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1500px;
}
.hero {
    background: linear-gradient(115deg, #17294a, #173c63 60%, #155e75);
    padding: 28px 30px;
    border: 1px solid #2b5275;
    border-radius: 18px;
    margin-bottom: 24px;
}
.hero h1 {
    font-size: 30px;
    font-weight: 800;
    margin: 0 0 8px 0;
    color: #ffffff;
}
.hero p {
    color: #c6d8f2;
    margin: 0;
    font-size: 14px;
}
.eyebrow {
    text-transform: uppercase;
    color: #7dd3fc;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
    margin-bottom: 10px;
}
.kpi {
    background: #141f33;
    border: 1px solid #283851;
    border-radius: 15px;
    padding: 20px;
    min-height: 125px;
}
.kpi-label {
    color: #9fb1ce;
    font-size: 12px;
    font-weight: 600;
    margin-bottom: 13px;
}
.kpi-value {
    color: #f4f7ff;
    font-size: 27px;
    font-weight: 800;
    overflow-wrap: anywhere;
}
.kpi-note {
    color: #7dd3fc;
    font-size: 11px;
    margin-top: 8px;
}
.section-title {
    font-size: 19px;
    font-weight: 700;
    color: #edf2ff;
    margin: 16px 0 5px 0;
}
.section-sub {
    color: #94a8c7;
    font-size: 12px;
    margin-bottom: 15px;
}
div[data-testid="stMetric"] {
    background: #141f33;
    border: 1px solid #283851;
    padding: 15px;
    border-radius: 12px;
}
div[data-testid="stMetricLabel"] {
    color: #a9bad4;
}
div[data-testid="stMetricValue"] {
    color: #f4f7ff;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}
.stTabs [data-baseweb="tab"] {
    background: #141f33;
    border-radius: 8px;
    padding: 10px 18px;
}
div[data-testid="stPlotlyChart"] {
    background: #111a2b;
    border: 1px solid #26364f;
    border-radius: 14px;
    padding: 10px;
}
div[data-testid="stDataFrame"] {
    border: 1px solid #26364f;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

CHART_TEMPLATE = "plotly_dark"

def load_json():
    path = REPORTS / "analysis_summary.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}

def load_datasets():
    # Prefer generated data; use sample input data if needed.
    files = list(PROCESSED.glob("*.csv")) if PROCESSED.exists() else []
    source = "Processed outputs"

    if not files and SAMPLE.exists():
        files = list(SAMPLE.glob("*.csv"))
        source = "Sample input data"

    result = {}
    for path in files:
        try:
            result[path.stem] = pd.read_csv(path, low_memory=False)
        except Exception:
            continue
    return result, source

def find_column(df, candidates):
    lookup = {str(c).lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]
    return None

def money(value):
    return f"R$ {value:,.2f}"

def kpi(label, value, note):
    st.markdown(
        f"""<div class="kpi">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-note">{note}</div>
        </div>""",
        unsafe_allow_html=True,
    )

datasets, source_label = load_datasets()
summary = load_json()

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("## ◈ OLIST")
    st.caption("ANALYTICS STUDIO")
    st.divider()
    page = st.radio(
        "WORKSPACE",
        ["Executive Overview", "Sales & Payments", "Customer Experience", "Data Explorer"],
    )
    st.divider()
    st.markdown("**DATA STATUS**")
    st.caption(f"Source: {source_label}")
    st.caption(f"Datasets loaded: {len(datasets)}")
    st.caption("Built with Python · Pandas · Plotly · Streamlit")
    if st.button("Refresh dashboard", use_container_width=True):
        st.rerun()

# ---------- HEADER ----------
st.markdown("""
<div class="hero">
  <div class="eyebrow">E-COMMERCE INTELLIGENCE</div>
  <h1>Olist Performance Dashboard</h1>
  <p>Explore sales, payments, customer satisfaction and operational data in one workspace.</p>
</div>
""", unsafe_allow_html=True)

if not datasets:
    st.warning("No CSV datasets were found. Run the sample pipeline and check the data folders.")
    st.info("Expected folders: data/processed or data/raw_sample.")
    st.stop()

# Pick likely datasets by filename.
def get_df(keyword):
    for name, frame in datasets.items():
        if keyword in name.lower():
            return frame
    return pd.DataFrame()

orders = get_df("orders")
items = get_df("order_items")
payments = get_df("payments")
reviews = get_df("reviews")
sellers = get_df("sellers")
customers = get_df("customers")
products = get_df("products")

order_id_col = find_column(orders, ["order_id"])
price_col = find_column(items, ["price"])
payment_col = find_column(payments, ["payment_value"])
review_score_col = find_column(reviews, ["review_score"])
status_col = find_column(orders, ["order_status"])
date_col = find_column(
    orders,
    ["order_purchase_timestamp", "order_approved_at", "order_delivered_customer_date"],
)

# ---------- EXECUTIVE OVERVIEW ----------
if page == "Executive Overview":
    st.markdown('<div class="section-title">Business at a glance</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">KPIs are calculated from available rows; they are not estimates of the full Olist business.</div>',
        unsafe_allow_html=True,
    )

    total_orders = orders[order_id_col].nunique() if order_id_col else (
        len(orders) if not orders.empty else 0
    )
    total_sellers = len(sellers) if not sellers.empty else 0
    total_customers = len(customers) if not customers.empty else 0

    total_sales = None
    sales_note = "Payment values"
    if payment_col and not payments.empty:
        total_sales = pd.to_numeric(payments[payment_col], errors="coerce").sum()
    elif price_col and not items.empty:
        total_sales = pd.to_numeric(items[price_col], errors="coerce").sum()
        sales_note = "Item price total"

    avg_review = None
    if review_score_col and not reviews.empty:
        avg_review = pd.to_numeric(reviews[review_score_col], errors="coerce").mean()

    cols = st.columns(4)
    with cols[0]:
        kpi("TOTAL ORDERS", f"{total_orders:,}", "Distinct order IDs when available")
    with cols[1]:
        kpi("TOTAL SELLERS", f"{total_sellers:,}", "Seller rows in loaded dataset")
    with cols[2]:
        kpi("TOTAL CUSTOMERS", f"{total_customers:,}", "Customer rows in loaded dataset")
    with cols[3]:
        kpi("AVERAGE REVIEW", f"{avg_review:.2f} / 5" if pd.notna(avg_review) else "N/A",
            "Calculated from available review scores")

    cols = st.columns(2)
    with cols[0]:
        if total_sales is not None and pd.notna(total_sales):
            kpi("PAYMENTS / ITEM VALUE", money(total_sales), sales_note)
        else:
            kpi("PAYMENTS / ITEM VALUE", "N/A", "No matching numeric sales field found")
    with cols[1]:
        if status_col and not orders.empty:
            completed = orders[status_col].astype(str).str.lower().eq("delivered").sum()
            rate = completed / len(orders) * 100 if len(orders) else 0
            kpi("DELIVERED ORDER SHARE", f"{rate:.1f}%", "Share of loaded order rows marked delivered")
        else:
            kpi("DELIVERED ORDER SHARE", "N/A", "Order status field not available")

    st.markdown('<div class="section-title">Explore your data</div>', unsafe_allow_html=True)
    a, b = st.columns(2)

    with a:
        if status_col and not orders.empty:
            counts = orders[status_col].fillna("Unknown").value_counts().reset_index()
            counts.columns = ["Order status", "Orders"]
            fig = px.pie(counts, names="Order status", values="Orders",
                         hole=0.62, title="Order status breakdown",
                         template=CHART_TEMPLATE)
            fig.update_layout(legend_title_text="", margin=dict(t=55, b=20, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)
        elif review_score_col and not reviews.empty:
            counts = reviews[review_score_col].value_counts().sort_index().reset_index()
            counts.columns = ["Review score", "Count"]
            fig = px.bar(counts, x="Review score", y="Count",
                         title="Customer review distribution", template=CHART_TEMPLATE)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Order status or review score data is not available.")

    with b:
        if price_col and not items.empty:
            prices = pd.to_numeric(items[price_col], errors="coerce").dropna()
            fig = px.histogram(prices.to_frame(name="Item price"), x="Item price",
                               nbins=25, title="Item price distribution",
                               template=CHART_TEMPLATE)
            fig.update_layout(yaxis_title="Number of items")
            st.plotly_chart(fig, use_container_width=True)
        elif payment_col and not payments.empty:
            vals = pd.to_numeric(payments[payment_col], errors="coerce").dropna()
            fig = px.histogram(vals.to_frame(name="Payment value"), x="Payment value",
                               nbins=25, title="Payment value distribution",
                               template=CHART_TEMPLATE)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No numeric price or payment data is available.")

    st.markdown('<div class="section-title">Analysis summary</div>', unsafe_allow_html=True)
    if summary:
        st.json(summary, expanded=False)
    else:
        st.caption("No analysis_summary.json file found.")

# ---------- SALES & PAYMENTS ----------
elif page == "Sales & Payments":
    st.markdown('<div class="section-title">Sales & payment analysis</div>', unsafe_allow_html=True)
    if not payments.empty and payment_col:
        payment_values = pd.to_numeric(payments[payment_col], errors="coerce")
        st.metric("Total payment value", money(payment_values.sum()))
        method_col = find_column(payments, ["payment_type"])
        if method_col:
            methods = payments.assign(_value=payment_values).groupby(
                method_col, dropna=False
            )["_value"].sum().reset_index()
            methods.columns = ["Payment method", "Total value"]
            fig = px.bar(methods, x="Payment method", y="Total value",
                         color="Total value", title="Payment value by method",
                         template=CHART_TEMPLATE)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(methods, use_container_width=True, hide_index=True)
        else:
            st.info("Payment method column not available.")
    else:
        st.info("A processed payment dataset with payment_value is needed for this view.")

    if not items.empty and price_col:
        item_prices = pd.to_numeric(items[price_col], errors="coerce")
        st.metric("Total item price", money(item_prices.sum()))
        category_col = find_column(items, ["product_category_name", "product_id"])
        if category_col:
            tmp = items.assign(_price=item_prices)
            grouped = tmp.groupby(category_col, dropna=False)["_price"].sum().nlargest(15).reset_index()
            grouped.columns = ["Category / product", "Item value"]
            fig = px.bar(grouped.sort_values("Item value"), x="Item value",
                         y="Category / product", orientation="h",
                         title="Top 15 categories / products by item value",
                         template=CHART_TEMPLATE)
            st.plotly_chart(fig, use_container_width=True)

# ---------- CUSTOMER EXPERIENCE ----------
elif page == "Customer Experience":
    st.markdown('<div class="section-title">Customer experience</div>', unsafe_allow_html=True)
    if not reviews.empty and review_score_col:
        review_data = reviews.copy()
        review_data[review_score_col] = pd.to_numeric(
            review_data[review_score_col], errors="coerce"
        )
        valid = review_data[review_score_col].dropna()
        c1, c2, c3 = st.columns(3)
        c1.metric("Reviews", f"{len(valid):,}")
        c2.metric("Average score", f"{valid.mean():.2f} / 5" if len(valid) else "N/A")
        c3.metric("One-star reviews", f"{(valid == 1).sum():,}")

        counts = valid.value_counts().sort_index().reset_index()
        counts.columns = ["Review score", "Number of reviews"]
        fig = px.bar(counts, x="Review score", y="Number of reviews",
                     color="Review score", title="Review score distribution",
                     template=CHART_TEMPLATE)
        st.plotly_chart(fig, use_container_width=True)

        title_col = find_column(reviews, ["review_comment_title"])
        message_col = find_column(reviews, ["review_comment_message"])
        if title_col or message_col:
            st.markdown("#### Review comments")
            show_cols = [c for c in [review_score_col, title_col, message_col] if c]
            st.dataframe(reviews[show_cols].head(100), use_container_width=True)
    else:
        st.info("No review_score field found in the loaded review dataset.")

    if not orders.empty:
        delivery_col = find_column(orders, ["order_delivered_customer_date"])
        estimate_col = find_column(orders, ["order_estimated_delivery_date"])
        if delivery_col and estimate_col:
            delivery = orders[[delivery_col, estimate_col]].copy()
            delivery[delivery_col] = pd.to_datetime(delivery[delivery_col], errors="coerce")
            delivery[estimate_col] = pd.to_datetime(delivery[estimate_col], errors="coerce")
            delivery["Days vs estimate"] = (
                delivery[delivery_col] - delivery[estimate_col]
            ).dt.total_seconds() / 86400
            valid_delivery = delivery.dropna(subset=["Days vs estimate"])
            if not valid_delivery.empty:
                late_share = (valid_delivery["Days vs estimate"] > 0).mean() * 100
                st.metric("Delivered after estimated date", f"{late_share:.1f}%")
                fig = px.histogram(valid_delivery, x="Days vs estimate", nbins=30,
                                   title="Delivery timing vs estimated date (days)",
                                   template=CHART_TEMPLATE)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Delivery date comparison is unavailable in the loaded order data.")

# ---------- DATA EXPLORER ----------
elif page == "Data Explorer":
    st.markdown('<div class="section-title">Dataset explorer</div>', unsafe_allow_html=True)
    names = list(datasets.keys())
    selected = st.selectbox("Select a dataset", names)
    df = datasets[selected]

    q1, q2, q3 = st.columns(3)
    q1.metric("Rows", f"{len(df):,}")
    q2.metric("Columns", f"{len(df.columns):,}")
    q3.metric("Missing cells", f"{int(df.isna().sum().sum()):,}")

    search = st.text_input("Search column names", placeholder="e.g. order, seller, review")
    if search:
        cols = [c for c in df.columns if search.lower() in str(c).lower()]
        view = df[cols] if cols else df
    else:
        view = df

    st.dataframe(view.head(500), use_container_width=True, hide_index=True)

    with st.expander("Column quality report"):
        quality = pd.DataFrame({
            "Column": df.columns,
            "Data type": [str(x) for x in df.dtypes],
            "Missing values": [int(x) for x in df.isna().sum()],
            "Missing %": [round(float(x) / max(len(df), 1) * 100, 2) for x in df.isna().sum()],
            "Unique values": [int(df[c].nunique(dropna=True)) for c in df.columns],
        })
        st.dataframe(quality, use_container_width=True, hide_index=True)

st.divider()
st.caption("Olist Analytics Studio • Portfolio project • Metrics reflect the datasets currently loaded.")
