"""Basic tests for the pipeline. Run with:  python -m pytest -q   (or: python tests/test_pipeline.py)

They build a small synthetic dataset, run the full pipeline, and check that the warehouse
and the metrics are internally consistent. They do NOT prove anything about the real data.
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import etl, metrics  # noqa: E402
from src.make_sample_data import generate  # noqa: E402


def _build(tmp: Path):
    raw = tmp / "raw"
    generate(raw, n_orders=1500, seed=7)
    db_path = tmp / "dw.db"
    engine = etl.run(raw, f"sqlite:///{db_path}", tmp / "processed")
    summary = metrics.run(engine, tmp / "processed", tmp / "reports", min_orders=10)
    return sqlite3.connect(db_path), summary, tmp


def test_pipeline_end_to_end():
    with tempfile.TemporaryDirectory() as d:
        conn, summary, tmp = _build(Path(d))

        q = lambda sql: pd.read_sql(sql, conn)  # noqa: E731
        assert q("SELECT COUNT(*) n FROM fact_orders").n[0] == 1500

        # no orphan keys
        assert q("""SELECT COUNT(*) n FROM fact_order_items i
                    LEFT JOIN fact_orders f ON f.order_id = i.order_id WHERE f.order_id IS NULL""").n[0] == 0
        assert q("""SELECT COUNT(*) n FROM fact_orders f
                    LEFT JOIN dim_customer c ON c.customer_id = f.customer_id WHERE c.customer_id IS NULL""").n[0] == 0

        # is_late must agree with delay_days
        bad = q("""SELECT COUNT(*) n FROM fact_orders
                   WHERE is_delivered = 1 AND is_late <> CASE WHEN delay_days > 0 THEN 1 ELSE 0 END""").n[0]
        assert bad == 0

        # non-delivered orders must not have delivery metrics
        assert q("SELECT COUNT(*) n FROM fact_orders WHERE is_delivered = 0 AND is_late IS NOT NULL").n[0] == 0

        # SQL and Python must agree on the headline on-time %
        sql_pct = q("""SELECT 100.0 * SUM(CASE WHEN is_late = 0 THEN 1 ELSE 0 END) / SUM(is_delivered) p
                       FROM fact_orders""").p[0]
        assert abs(sql_pct - summary["kpis"]["on_time_pct"]) < 0.01

        # the synthetic data plants a strong lateness -> low review effect
        r = summary["delay_vs_review"]
        assert r["avg_review_on_time"] > r["avg_review_late"] + 0.5
        assert r["welch_p_value"] < 0.001

        # outputs exist
        for name in ("kpi_summary", "seller_scorecard", "delivery_by_state", "monthly_trend"):
            assert (tmp / "processed" / f"{name}.csv").exists(), name
        assert (tmp / "reports" / "weekly_summary.md").exists()


def test_seller_tiers_flag_planted_bad_sellers():
    with tempfile.TemporaryDirectory() as d:
        _, _, tmp = _build(Path(d))
        sc = pd.read_csv(tmp / "processed" / "seller_scorecard.csv")
        red = sc[sc["tier"] == "Red"]
        assert len(red) >= 1
        assert red["late_pct"].min() > sc["late_pct"].median()


if __name__ == "__main__":  # run without pytest
    test_pipeline_end_to_end()
    test_seller_tiers_flag_planted_bad_sellers()
    print("all tests passed")
