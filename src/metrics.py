"""Metrics layer: KPIs, seller scorecard, anomaly flags, delay-vs-review statistics,
review-text keywords and a what-if impact estimate. Reads from the warehouse, writes CSV/JSON.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from . import db

LOG = logging.getLogger("metrics")

STOPWORDS = set("""de da do das dos que para com uma um por nao não mais muito foi ficou como mas porem porém
em no na nos nas se so só ao aos ate até ja já pelo pela meu minha tem tinha estou esta está sao são
the and was for not that this with have has""".split())
DELAY_WORDS = ("atraso", "atrasou", "prazo", "demor", "nao chegou", "não chegou", "ainda nao", "ainda não", "entrega")


def _read(engine, sql: str) -> pd.DataFrame:
    return db.read_df(engine, sql)


def load_frames(engine) -> dict[str, pd.DataFrame]:
    orders = _read(engine, """
        SELECT f.*, c.state AS customer_state, c.customer_unique_id, d.month_label, d.is_holiday, d.is_weekend
        FROM fact_orders f
        JOIN dim_customer c ON c.customer_id = f.customer_id
        JOIN dim_date d ON d.date_key = f.purchase_date""")
    items = _read(engine, """
        SELECT i.*, p.category, s.state AS seller_state
        FROM fact_order_items i
        LEFT JOIN dim_product p ON p.product_id = i.product_id
        LEFT JOIN dim_seller s ON s.seller_id = i.seller_id""")
    reviews = _read(engine, "SELECT review_score, comment_message FROM fact_reviews")
    return {"orders": orders, "items": items, "reviews": reviews}


def _pct(num, den) -> float:
    return round(100.0 * num / den, 2) if den else float("nan")


# ------------------------------------------------------------------------------ pieces
def kpi_summary(orders: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    delivered = orders[orders["is_delivered"] == 1]
    people = orders[orders["order_status"] != "canceled"].groupby("customer_unique_id")["order_id"].nunique()
    rows = [
        ("total_orders", len(orders)),
        ("delivered_orders", len(delivered)),
        ("on_time_pct", _pct((delivered["is_late"] == 0).sum(), len(delivered))),
        ("late_pct", _pct((delivered["is_late"] == 1).sum(), len(delivered))),
        ("avg_review_score", round(orders["review_score"].mean(), 2)),
        ("item_revenue", round(items["price"].sum(), 2)),
        ("avg_delivery_days", round(delivered["delivery_days"].mean(), 2)),
        ("unique_customers", len(people)),
        ("repeat_customer_pct", _pct((people > 1).sum(), len(people))),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


def delivery_by_state(orders: pd.DataFrame) -> pd.DataFrame:
    d = orders[orders["is_delivered"] == 1]
    g = d.groupby("customer_state").agg(delivered_orders=("order_id", "count"), late_orders=("is_late", "sum"),
                                         avg_review=("review_score", "mean"), avg_delivery_days=("delivery_days", "mean"))
    g["late_pct"] = (100 * g["late_orders"] / g["delivered_orders"]).round(2)
    g["avg_review"] = g["avg_review"].round(2)
    g["avg_delivery_days"] = g["avg_delivery_days"].round(2)
    g["late_rank"] = g["late_pct"].rank(ascending=False, method="min").astype(int)
    return g.reset_index().sort_values("late_rank")


def monthly_trend(orders: pd.DataFrame) -> pd.DataFrame:
    d = orders[orders["is_delivered"] == 1]
    g = d.groupby("month_label").agg(delivered_orders=("order_id", "count"), late_orders=("is_late", "sum"),
                                      avg_review=("review_score", "mean")).reset_index()
    g["late_pct"] = (100 * g["late_orders"] / g["delivered_orders"]).round(2)
    g["avg_review"] = g["avg_review"].round(2)
    g["change_vs_prev_month_pp"] = g["late_pct"].diff().round(2)
    # flag months far above the typical level (only meaningful with enough months)
    big = g[g["delivered_orders"] >= 30]["late_pct"]
    std = big.std(ddof=0)
    g["anomaly_flag"] = ((g["late_pct"] - big.mean()) / std > 2) if len(big) >= 6 and std > 0 else False
    return g


def category_performance(orders: pd.DataFrame, items: pd.DataFrame, min_orders: int) -> pd.DataFrame:
    oc = items[["order_id", "category"]].drop_duplicates()
    d = orders[orders["is_delivered"] == 1][["order_id", "is_late", "review_score"]]
    m = oc.merge(d, on="order_id")
    g = m.groupby("category").agg(delivered_orders=("order_id", "count"), late_orders=("is_late", "sum"),
                                  avg_review=("review_score", "mean")).reset_index()
    g["late_pct"] = (100 * g["late_orders"] / g["delivered_orders"]).round(2)
    g["avg_review"] = g["avg_review"].round(2)
    rev = items.groupby("category")["price"].sum().round(2).rename("revenue").reset_index()
    g = g.merge(rev, on="category", how="left")
    return g[g["delivered_orders"] >= min_orders].sort_values("late_pct", ascending=False)


def seller_scorecard(orders: pd.DataFrame, items: pd.DataFrame, min_orders: int) -> pd.DataFrame:
    d = orders[orders["is_delivered"] == 1][["order_id", "is_late", "review_score"]]
    so = items[["order_id", "seller_id"]].drop_duplicates().merge(d, on="order_id")
    g = so.groupby("seller_id").agg(orders=("order_id", "count"), late_orders=("is_late", "sum"),
                                    avg_review=("review_score", "mean")).reset_index()
    rev = items.groupby("seller_id")["price"].sum().round(2).rename("revenue").reset_index()
    g = g.merge(rev, on="seller_id", how="left")
    g["late_pct"] = (100 * g["late_orders"] / g["orders"]).round(2)
    g["avg_review"] = g["avg_review"].round(2)

    overall_late = 100 * g["late_orders"].sum() / g["orders"].sum()
    eligible = g["orders"] >= min_orders
    pct_rank = g.loc[eligible, "late_pct"].rank(pct=True, method="average")
    g["tier"] = "Insufficient data"
    g.loc[eligible, "tier"] = "Green"
    g.loc[pct_rank[(pct_rank >= 0.70) & (g.loc[pct_rank.index, "late_pct"] > overall_late)].index, "tier"] = "Amber"
    g.loc[pct_rank[(pct_rank >= 0.90) & (g.loc[pct_rank.index, "late_pct"] > overall_late)].index, "tier"] = "Red"

    sub = g.loc[eligible, "late_pct"]
    z = (sub - sub.mean()) / sub.std(ddof=0) if len(sub) > 2 and sub.std(ddof=0) > 0 else pd.Series(0.0, index=sub.index)
    g["late_pct_zscore"] = np.nan
    g.loc[eligible, "late_pct_zscore"] = z.round(2)
    g["anomaly_flag"] = g["late_pct_zscore"] > 2
    return g.sort_values("late_pct", ascending=False)


def delay_vs_review(orders: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    d = orders[(orders["is_delivered"] == 1) & orders["review_score"].notna()].copy()
    bins = [-np.inf, -7, 0, 3, 7, np.inf]
    labels = ["1. 7+ days early", "2. on time (0-6 early)", "3. 1-3 days late", "4. 4-7 days late", "5. 8+ days late"]
    d["delivery_bucket"] = pd.cut(d["delay_days"].astype(float), bins=bins, labels=labels)
    g = d.groupby("delivery_bucket", observed=True).agg(orders=("order_id", "count"), avg_review=("review_score", "mean"),
                                                         one_star_pct=("review_score", lambda s: 100 * (s == 1).mean())).round(2).reset_index()
    late, ontime = d[d["is_late"] == 1]["review_score"].astype(float), d[d["is_late"] == 0]["review_score"].astype(float)
    result = {"orders_with_review": int(len(d)), "avg_review_late": round(float(late.mean()), 2),
              "avg_review_on_time": round(float(ontime.mean()), 2),
              "review_gap": round(float(ontime.mean() - late.mean()), 2)}
    if len(late) > 1 and len(ontime) > 1:
        t, p = stats.ttest_ind(late, ontime, equal_var=False)
        result["welch_t_stat"], result["welch_p_value"] = round(float(t), 3), float(p)
        result["corr_is_late_vs_review"] = round(float(d["is_late"].astype(float).corr(d["review_score"].astype(float))), 3)
    return g, result


def review_keywords(reviews: pd.DataFrame, top_n: int = 15) -> tuple[pd.DataFrame, dict]:
    r = reviews.dropna(subset=["comment_message"]).copy()
    r["review_score"] = r["review_score"].astype(int)

    def top(df):
        c = Counter(w for msg in df["comment_message"] for w in re.findall(r"[a-zà-ú]+", str(msg).lower())
                    if len(w) >= 4 and w not in STOPWORDS)
        return c.most_common(top_n)

    low, high = r[r["review_score"] <= 2], r[r["review_score"] >= 4]
    rows = [("low (1-2 stars)", w, n) for w, n in top(low)] + [("high (4-5 stars)", w, n) for w, n in top(high)]
    kw = pd.DataFrame(rows, columns=["group", "word", "count"])
    mentions = low["comment_message"].str.lower().apply(lambda s: any(k in s for k in DELAY_WORDS)).sum() if len(low) else 0
    return kw, {"low_score_comments": int(len(low)), "low_score_comments_mentioning_delivery": int(mentions),
                "pct_low_comments_about_delivery": _pct(mentions, len(low))}


def impact_estimate(scorecard: pd.DataFrame, min_orders: int) -> dict:
    """What-if: if the Red-tier sellers matched everyone else's late rate, how many late orders disappear?"""
    el = scorecard[scorecard["orders"] >= min_orders]
    red, rest = el[el["tier"] == "Red"], el[el["tier"] != "Red"]
    if red.empty or rest.empty:
        return {"note": "no Red-tier sellers or no comparison group"}
    rest_rate = rest["late_orders"].sum() / rest["orders"].sum()
    now, fixed = int(red["late_orders"].sum()), float(red["orders"].sum() * rest_rate)
    total_late = int(scorecard["late_orders"].sum())
    return {"red_sellers": int(len(red)), "red_seller_orders": int(red["orders"].sum()),
            "red_share_of_all_late_orders_pct": _pct(now, total_late),
            "late_orders_now": now, "late_orders_if_matching_rest": round(fixed, 1),
            "late_orders_avoided": round(now - fixed, 1),
            "assumption": "What-if estimate only. Assumes Red sellers can reach the late rate of all other eligible sellers."}


# ------------------------------------------------------------------------------- run
def run(engine, out_dir: Path, report_dir: Path, min_orders: int = 30) -> dict:
    f = load_frames(engine)
    orders, items, reviews = f["orders"], f["items"], f["reviews"]
    out_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    kpis = kpi_summary(orders, items)
    by_state = delivery_by_state(orders)
    monthly = monthly_trend(orders)
    cats = category_performance(orders, items, min_orders)
    sellers = seller_scorecard(orders, items, min_orders)
    buckets, review_stats = delay_vs_review(orders)
    keywords, kw_stats = review_keywords(reviews)
    impact = impact_estimate(sellers, min_orders)

    outputs = {"kpi_summary": kpis, "delivery_by_state": by_state, "monthly_trend": monthly,
               "category_performance": cats, "seller_scorecard": sellers, "delay_vs_review": buckets,
               "review_keywords": keywords}
    for name, df in outputs.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
    summary = {"kpis": dict(zip(kpis["metric"], kpis["value"])), "delay_vs_review": review_stats,
               "review_text": kw_stats, "impact_estimate": impact, "min_orders_per_seller": min_orders}
    (report_dir / "analysis_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    write_markdown_report(summary, by_state, sellers, report_dir / "weekly_summary.md")
    LOG.info("metrics written to %s and %s", out_dir, report_dir)
    return summary


def impact_lines(imp: dict) -> list[str]:
    if "late_orders_avoided" not in imp:
        return [f"- {imp.get('note', 'not available')}"]
    return [
        f"- {imp['red_sellers']} Red-tier sellers handle {imp['red_seller_orders']:,} orders and cause "
        f"{imp['red_share_of_all_late_orders_pct']}% of all late orders ({imp['late_orders_now']} late orders).",
        f"- If they matched the late rate of all other sellers, about {imp['late_orders_avoided']:.0f} late orders "
        f"would be avoided.",
        f"- Assumption: {imp['assumption']}",
    ]


def write_markdown_report(summary: dict, by_state: pd.DataFrame, sellers: pd.DataFrame, path: Path) -> None:
    k, r, imp = summary["kpis"], summary["delay_vs_review"], summary["impact_estimate"]
    worst_states = by_state.head(3)[["customer_state", "late_pct"]].values.tolist()
    red = sellers[sellers["tier"] == "Red"].head(5)
    lines = [
        "# Weekly Seller & Customer Experience Summary",
        "",
        "_Auto-generated by `src/run_pipeline.py`. Check that the numbers come from the real dataset before sharing._",
        "",
        "## Headline KPIs",
        f"- Orders: **{int(k['total_orders']):,}** ({int(k['delivered_orders']):,} delivered)",
        f"- On-time delivery: **{k['on_time_pct']}%** (late: {k['late_pct']}%)",
        f"- Average review score: **{k['avg_review_score']}**",
        f"- Item revenue: **{float(k['item_revenue']):,.2f}**",
        f"- Repeat-customer rate: **{k['repeat_customer_pct']}%**",
        "",
        "## Delivery vs satisfaction",
        f"- Average review when on time: {r.get('avg_review_on_time')} vs when late: {r.get('avg_review_late')} "
        f"(gap {r.get('review_gap')} points)",
        f"- Welch t-test p-value: {r.get('welch_p_value')}",
        "",
        "## Regions with the highest late rate",
        *[f"- {s}: {p}%" for s, p in worst_states],
        "",
        "## Red-tier sellers (highest late rates)",
        *([f"- {row.seller_id}: {row.late_pct}% late over {row.orders} orders, avg review {row.avg_review}"
           for row in red.itertuples()] or ["- none"]),
        "",
        "## What-if impact (estimate, not a forecast)",
        *impact_lines(imp),
        "",
    ]
    path.write_text("\n".join(lines))
