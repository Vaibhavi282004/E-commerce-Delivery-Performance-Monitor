"""ETL: raw Olist CSVs -> cleaned star schema in a SQL database (+ CSV exports for Power BI).

Default database is SQLite via Python's built-in sqlite3 (no install needed).
Pass a PostgreSQL URL to use Postgres instead (needs sqlalchemy + psycopg2):
    postgresql+psycopg2://user:password@localhost:5432/olist
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from . import db

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger("etl")

REQUIRED_FILES = {
    "orders": "olist_orders_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "translation": "product_category_name_translation.csv",
}


# ----------------------------------------------------------------------------- extract
def extract(raw_dir: Path) -> dict[str, pd.DataFrame]:
    raw_dir = Path(raw_dir)
    missing = [f for f in REQUIRED_FILES.values() if not (raw_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing files in {raw_dir}: {missing}. Download the Olist dataset from Kaggle "
            "and unzip the CSVs there, or run with --sample to use synthetic data."
        )
    data = {key: pd.read_csv(raw_dir / fname) for key, fname in REQUIRED_FILES.items()}
    for key, df in data.items():
        LOG.info("extracted %-12s %8d rows", key, len(df))
    return data


# --------------------------------------------------------------------------- transform
def _iso_date(ts: pd.Series) -> pd.Series:
    s = ts.dt.strftime("%Y-%m-%d")
    return s.where(ts.notna(), None)


def build_dim_customer(customers: pd.DataFrame) -> pd.DataFrame:
    df = customers.drop_duplicates("customer_id").rename(
        columns={"customer_city": "city", "customer_state": "state"})
    df["city"] = df["city"].str.strip().str.lower()
    df["state"] = df["state"].str.strip().str.upper()
    return df[["customer_id", "customer_unique_id", "city", "state"]]


def build_dim_seller(sellers: pd.DataFrame) -> pd.DataFrame:
    df = sellers.drop_duplicates("seller_id").rename(columns={"seller_city": "city", "seller_state": "state"})
    df["city"] = df["city"].str.strip().str.lower()
    df["state"] = df["state"].str.strip().str.upper()
    return df[["seller_id", "city", "state"]]


def build_dim_product(products: pd.DataFrame, translation: pd.DataFrame) -> pd.DataFrame:
    df = products.drop_duplicates("product_id").merge(translation, on="product_category_name", how="left")
    df["category"] = df["product_category_name_english"].fillna(df["product_category_name"]).fillna("unknown")
    df = df.rename(columns={"product_weight_g": "weight_g", "product_photos_qty": "photos_qty"})
    df["photos_qty"] = df["photos_qty"].astype("Int64")
    return df[["product_id", "category", "weight_g", "photos_qty"]]


def build_fact_reviews(reviews: pd.DataFrame) -> pd.DataFrame:
    df = reviews.drop_duplicates(["review_id", "order_id"]).copy()
    df["review_score"] = pd.to_numeric(df["review_score"], errors="coerce")
    df = df[df["review_score"].between(1, 5)]
    df["review_score"] = df["review_score"].astype("Int64")
    created = pd.to_datetime(df["review_creation_date"], errors="coerce")
    df["created_date"] = _iso_date(created)
    df = df.rename(columns={"review_comment_title": "comment_title", "review_comment_message": "comment_message"})
    for col in ("comment_title", "comment_message"):
        df[col] = df[col].where(df[col].notna(), None)
    return df[["review_id", "order_id", "review_score", "comment_title", "comment_message", "created_date"]]


def build_fact_order_items(items: pd.DataFrame, valid_orders: set) -> pd.DataFrame:
    df = items[items["order_id"].isin(valid_orders)].copy()
    df = df.drop_duplicates(["order_id", "order_item_id"])
    return df[["order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"]]


def build_fact_orders(orders: pd.DataFrame, items: pd.DataFrame, payments: pd.DataFrame,
                      reviews_raw: pd.DataFrame) -> pd.DataFrame:
    df = orders.drop_duplicates("order_id").copy()
    purchase = pd.to_datetime(df["order_purchase_timestamp"], errors="coerce")
    delivered = pd.to_datetime(df["order_delivered_customer_date"], errors="coerce")
    estimated = pd.to_datetime(df["order_estimated_delivery_date"], errors="coerce")

    df = df[purchase.notna()].copy()
    purchase, delivered, estimated = purchase[df.index], delivered[df.index], estimated[df.index]

    is_delivered = (df["order_status"] == "delivered") & delivered.notna()
    delay = (delivered.dt.normalize() - estimated.dt.normalize()).dt.days  # >0 = late
    df["purchase_date"] = _iso_date(purchase)
    df["delivered_date"] = _iso_date(delivered.where(is_delivered))
    df["estimated_date"] = _iso_date(estimated)
    df["delivery_days"] = ((delivered - purchase).dt.total_seconds() / 86400).round(2).where(is_delivered)
    df["estimated_days"] = ((estimated - purchase).dt.total_seconds() / 86400).round(2)
    df["delay_days"] = delay.where(is_delivered).astype("Int64")
    df["is_delivered"] = is_delivered.astype(int)
    df["is_late"] = (delay > 0).where(is_delivered).astype("Int64")

    # latest review per order
    rv = reviews_raw.copy()
    rv["review_score"] = pd.to_numeric(rv["review_score"], errors="coerce")
    rv = rv[rv["review_score"].between(1, 5)]
    rv["_ts"] = pd.to_datetime(rv["review_answer_timestamp"], errors="coerce")
    rv = rv.sort_values("_ts").drop_duplicates("order_id", keep="last")
    df = df.merge(rv[["order_id", "review_score"]], on="order_id", how="left")
    df["review_score"] = df["review_score"].astype("Int64")

    item_agg = items.groupby("order_id").agg(
        items_count=("order_item_id", "count"), order_value=("price", "sum"),
        freight_value=("freight_value", "sum")).reset_index()
    pay_agg = payments.groupby("order_id").agg(payment_value=("payment_value", "sum")).reset_index()
    df = df.merge(item_agg, on="order_id", how="left").merge(pay_agg, on="order_id", how="left")
    df["items_count"] = df["items_count"].fillna(0).astype(int)
    for col in ("order_value", "freight_value", "payment_value"):
        df[col] = df[col].fillna(0).round(2)

    cols = ["order_id", "customer_id", "purchase_date", "order_status", "delivered_date", "estimated_date",
            "delivery_days", "estimated_days", "delay_days", "is_delivered", "is_late", "review_score",
            "items_count", "order_value", "freight_value", "payment_value"]
    return df[cols]


def build_dim_date(fact_orders: pd.DataFrame, holidays_csv: Path) -> pd.DataFrame:
    dates = pd.to_datetime(fact_orders["purchase_date"])
    days = pd.date_range(dates.min() - pd.Timedelta(days=7), dates.max() + pd.Timedelta(days=7), freq="D")
    dim = pd.DataFrame({"d": days})
    dim["date_key"] = dim["d"].dt.strftime("%Y-%m-%d")
    dim["year"] = dim["d"].dt.year
    dim["month"] = dim["d"].dt.month
    dim["month_label"] = dim["d"].dt.strftime("%Y-%m")
    dim["quarter"] = dim["d"].dt.quarter
    dim["day_of_week"] = dim["d"].dt.day_name()
    dim["is_weekend"] = (dim["d"].dt.dayofweek >= 5).astype(int)
    hol = pd.read_csv(holidays_csv) if Path(holidays_csv).exists() else pd.DataFrame(columns=["date", "holiday_name"])
    hol = hol.drop_duplicates("date").rename(columns={"date": "date_key"})
    dim = dim.merge(hol, on="date_key", how="left")
    dim["is_holiday"] = dim["holiday_name"].notna().astype(int)
    dim["holiday_name"] = dim["holiday_name"].where(dim["holiday_name"].notna(), None)
    return dim[["date_key", "year", "month", "month_label", "quarter", "day_of_week",
                "is_weekend", "is_holiday", "holiday_name"]]


# ---------------------------------------------------------------------------- validate
def validate(t: dict[str, pd.DataFrame]) -> None:
    """Fail loudly if the warehouse has broken keys or impossible values."""
    fo = t["fact_orders"]
    assert fo["order_id"].is_unique, "fact_orders.order_id must be unique"
    assert t["dim_customer"]["customer_id"].is_unique, "dim_customer.customer_id must be unique"
    assert fo["customer_id"].isin(t["dim_customer"]["customer_id"]).all(), "orders with unknown customer"
    items = t["fact_order_items"]
    assert items["order_id"].isin(fo["order_id"]).all(), "items with unknown order"
    orphan_sellers = (~items["seller_id"].isin(t["dim_seller"]["seller_id"])).sum()
    orphan_products = (~items["product_id"].isin(t["dim_product"]["product_id"])).sum()
    if orphan_sellers or orphan_products:
        LOG.warning("items with unknown seller: %d, unknown product: %d", orphan_sellers, orphan_products)
    scores = fo["review_score"].dropna()
    assert scores.between(1, 5).all(), "review_score outside 1-5"
    delivered = fo[fo["is_delivered"] == 1]
    assert delivered["delivered_date"].notna().all(), "delivered order without delivered_date"
    assert (delivered["is_late"] == (delivered["delay_days"] > 0).astype(int)).all(), "is_late inconsistent"
    LOG.info("validation passed: %d orders, %d items, %d delivered", len(fo), len(items), len(delivered))


# --------------------------------------------------------------------------------- load
def load(engine, tables: dict[str, pd.DataFrame], ddl_path: Path) -> None:
    db.run_script(engine, ddl_path)
    order = ["dim_date", "dim_customer", "dim_seller", "dim_product", "fact_orders", "fact_order_items", "fact_reviews"]
    for name in order:
        tables[name].to_sql(name, engine, if_exists="append", index=False, chunksize=2000)
        LOG.info("loaded %-17s %8d rows", name, len(tables[name]))


def export_csvs(tables: dict[str, pd.DataFrame], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)


# ---------------------------------------------------------------------------------- run
def run(raw_dir: Path, db_url: str, out_dir: Path, holidays_csv: Path | None = None):
    holidays_csv = holidays_csv or ROOT / "data" / "reference" / "brazil_holidays.csv"
    scraped = ROOT / "data" / "reference" / "brazil_holidays_scraped.csv"
    if holidays_csv == ROOT / "data" / "reference" / "brazil_holidays.csv" and scraped.exists():
        LOG.info("using scraped holiday file %s", scraped.name)
        holidays_csv = scraped

    raw = extract(raw_dir)
    fact_orders = build_fact_orders(raw["orders"], raw["items"], raw["payments"], raw["reviews"])
    tables = {
        "dim_customer": build_dim_customer(raw["customers"]),
        "dim_seller": build_dim_seller(raw["sellers"]),
        "dim_product": build_dim_product(raw["products"], raw["translation"]),
        "fact_orders": fact_orders,
        "fact_order_items": build_fact_order_items(raw["items"], set(fact_orders["order_id"])),
        "fact_reviews": build_fact_reviews(raw["reviews"]),
        "dim_date": build_dim_date(fact_orders, holidays_csv),
    }
    tables["fact_reviews"] = tables["fact_reviews"][tables["fact_reviews"]["order_id"].isin(fact_orders["order_id"])]
    validate(tables)

    engine = db.connect(db_url)
    load(engine, tables, ROOT / "sql" / "01_schema.sql")
    export_csvs(tables, out_dir)
    return engine
