"""Generate a small SYNTHETIC dataset with the same file names and columns as the
Olist Kaggle files, so you can run the whole pipeline before downloading the real data.

All numbers produced from this data are fake. Never put them in your resume or report.
Some sellers and states are deliberately made worse so the analysis has patterns to find.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

STATE_RISK = {"SP": 0.05, "RJ": 0.10, "MG": 0.07, "RS": 0.06, "PR": 0.06,
              "BA": 0.14, "PE": 0.16, "CE": 0.15, "AM": 0.25, "PA": 0.22}
CATEGORIES = [("cama_mesa_banho", "bed_bath_table"), ("beleza_saude", "health_beauty"),
              ("esporte_lazer", "sports_leisure"), ("informatica_acessorios", "computers_accessories"),
              ("moveis_decoracao", "furniture_decor"), ("telefonia", "telephony"),
              ("brinquedos", "toys"), ("relogios_presentes", "watches_gifts")]
POSITIVE = ["produto otimo chegou rapido", "recomendo muito a loja", "entrega dentro do prazo",
            "tudo certo com o pedido", "qualidade excelente"]
NEGATIVE = ["produto nao chegou no prazo", "atraso na entrega", "ainda nao recebi o pedido",
            "demorou muito para chegar", "pessimo atendimento do vendedor"]
FMT = "%Y-%m-%d %H:%M:%S"


def generate(out_dir: Path, n_orders: int = 4000, seed: int = 42) -> None:
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Sellers: 60, of which 6 are "bad" (much higher late probability)
    n_sellers = 60
    seller_ids = [f"seller{i:04d}" for i in range(n_sellers)]
    bad_sellers = set(rng.choice(seller_ids, size=6, replace=False))
    states = list(STATE_RISK)
    sellers = pd.DataFrame({
        "seller_id": seller_ids,
        "seller_zip_code_prefix": rng.integers(1000, 99999, n_sellers),
        "seller_city": [f"city{i % 15}" for i in range(n_sellers)],
        "seller_state": rng.choice(states, n_sellers),
    })

    # Products
    n_products = 300
    product_ids = [f"prod{i:05d}" for i in range(n_products)]
    products = pd.DataFrame({
        "product_id": product_ids,
        "product_category_name": rng.choice([c[0] for c in CATEGORIES], n_products),
        "product_name_lenght": rng.integers(20, 60, n_products),
        "product_description_lenght": rng.integers(100, 1500, n_products),
        "product_photos_qty": rng.integers(1, 8, n_products),
        "product_weight_g": rng.integers(100, 8000, n_products),
        "product_length_cm": rng.integers(10, 60, n_products),
        "product_height_cm": rng.integers(5, 40, n_products),
        "product_width_cm": rng.integers(10, 50, n_products),
    })
    translation = pd.DataFrame(CATEGORIES, columns=["product_category_name", "product_category_name_english"])

    # Customers: one customer_id per order, repeat buyers share customer_unique_id
    n_people = int(n_orders * 0.9)
    person_for_order = rng.integers(0, n_people, n_orders)
    cust_state = rng.choice(states, n_orders, p=np.array([0.35, 0.15, 0.12, 0.07, 0.07, 0.06, 0.05, 0.05, 0.04, 0.04]))
    customers = pd.DataFrame({
        "customer_id": [f"cust{i:06d}" for i in range(n_orders)],
        "customer_unique_id": [f"person{p:06d}" for p in person_for_order],
        "customer_zip_code_prefix": rng.integers(1000, 99999, n_orders),
        "customer_city": [f"town{i % 40}" for i in range(n_orders)],
        "customer_state": cust_state,
    })

    # Orders
    start, end = pd.Timestamp("2017-01-01"), pd.Timestamp("2018-08-31")
    span_seconds = int((end - start).total_seconds())
    purchase = start + pd.to_timedelta(rng.integers(0, span_seconds, n_orders), unit="s")
    order_seller = rng.choice(seller_ids, n_orders)
    p_late = np.array([STATE_RISK[s] for s in cust_state]) + np.array([0.30 if s in bad_sellers else 0.0 for s in order_seller])
    is_late = rng.random(n_orders) < np.clip(p_late, 0, 0.9)
    est_days = rng.integers(12, 29, n_orders)
    actual_days = np.where(is_late, est_days + rng.integers(1, 15, n_orders),
                           np.maximum(2, est_days - rng.integers(1, 10, n_orders)))
    status = rng.choice(["delivered", "canceled", "shipped"], n_orders, p=[0.97, 0.02, 0.01])
    est_ts = (purchase + pd.to_timedelta(est_days, unit="D")).normalize()
    deliv_ts = purchase + pd.to_timedelta(actual_days, unit="D") + pd.to_timedelta(rng.integers(0, 80000, n_orders), unit="s")
    # keep "late" meaning consistent at date level
    deliv_ts = pd.Series(np.where(is_late, np.maximum(deliv_ts, est_ts + pd.Timedelta(days=1, hours=1)), deliv_ts))
    deliv_ts = pd.to_datetime(deliv_ts)
    delivered_mask = status == "delivered"

    def fmt(series, mask=None):
        s = pd.Series(series).dt.strftime(FMT)
        if mask is not None:
            s = s.where(mask, None)
        return s

    orders = pd.DataFrame({
        "order_id": [f"order{i:06d}" for i in range(n_orders)],
        "customer_id": customers["customer_id"],
        "order_status": status,
        "order_purchase_timestamp": fmt(purchase),
        "order_approved_at": fmt(pd.Series(purchase) + pd.Timedelta(hours=2)),
        "order_delivered_carrier_date": fmt(pd.Series(purchase) + pd.Timedelta(days=2), status != "canceled"),
        "order_delivered_customer_date": fmt(deliv_ts, delivered_mask),
        "order_estimated_delivery_date": fmt(est_ts),
    })

    # Items: 1 to 3 per order, all from the order's seller (some orders get a second seller)
    rows = []
    for i in range(n_orders):
        for k in range(1, int(rng.choice([1, 2, 3], p=[0.8, 0.15, 0.05])) + 1):
            seller = order_seller[i] if (k == 1 or rng.random() < 0.8) else rng.choice(seller_ids)
            rows.append((orders.at[i, "order_id"], k, rng.choice(product_ids), seller,
                         orders.at[i, "order_purchase_timestamp"],
                         round(float(rng.lognormal(4.2, 0.7)), 2), round(float(rng.uniform(8, 45)), 2)))
    items = pd.DataFrame(rows, columns=["order_id", "order_item_id", "product_id", "seller_id",
                                        "shipping_limit_date", "price", "freight_value"])

    # Payments
    totals = items.groupby("order_id")[["price", "freight_value"]].sum().sum(axis=1).round(2)
    payments = pd.DataFrame({
        "order_id": totals.index, "payment_sequential": 1,
        "payment_type": rng.choice(["credit_card", "boleto", "voucher", "debit_card"], len(totals), p=[0.74, 0.19, 0.04, 0.03]),
        "payment_installments": rng.integers(1, 10, len(totals)),
        "payment_value": totals.values,
    })

    # Reviews: score depends strongly on lateness
    rev_rows = []
    for i in range(n_orders):
        if status[i] == "canceled" or rng.random() > 0.97:
            continue
        probs = [0.30, 0.15, 0.20, 0.15, 0.20] if (is_late[i] and delivered_mask[i]) else [0.03, 0.03, 0.08, 0.20, 0.66]
        score = int(rng.choice([1, 2, 3, 4, 5], p=probs))
        comment = None
        if rng.random() < 0.4:
            comment = str(rng.choice(NEGATIVE if score <= 2 else POSITIVE))
        created = (deliv_ts[i] if delivered_mask[i] else purchase[i] + pd.Timedelta(days=10)).strftime(FMT)
        rev_rows.append((f"review{i:06d}", orders.at[i, "order_id"], score, None, comment,
                         created, created))
    reviews = pd.DataFrame(rev_rows, columns=["review_id", "order_id", "review_score", "review_comment_title",
                                              "review_comment_message", "review_creation_date", "review_answer_timestamp"])

    files = {
        "olist_orders_dataset.csv": orders, "olist_order_items_dataset.csv": items,
        "olist_customers_dataset.csv": customers, "olist_sellers_dataset.csv": sellers,
        "olist_products_dataset.csv": products, "olist_order_reviews_dataset.csv": reviews,
        "olist_order_payments_dataset.csv": payments, "product_category_name_translation.csv": translation,
    }
    for name, df in files.items():
        df.to_csv(out_dir / name, index=False)
    print(f"Wrote {len(files)} synthetic files to {out_dir} (FAKE data, for testing only)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "data" / "raw_sample"))
    ap.add_argument("--orders", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    generate(Path(a.out), a.orders, a.seed)
