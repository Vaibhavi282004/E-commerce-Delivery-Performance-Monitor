"""One command to run everything: raw CSVs -> warehouse -> metrics -> reports.

    python -m src.run_pipeline --sample                       # synthetic data, to test the setup
    python -m src.run_pipeline --raw-dir data/raw             # real Olist data from Kaggle
    python -m src.run_pipeline --db-url postgresql+psycopg2://user:pw@localhost:5432/olist
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from . import etl, metrics
from .make_sample_data import generate

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", default=str(ROOT / "data" / "raw"), help="folder with the Olist CSV files")
    ap.add_argument("--db-url", default=f"sqlite:///{ROOT / 'data' / 'processed' / 'olist_dw.db'}")
    ap.add_argument("--out-dir", default=str(ROOT / "data" / "processed"))
    ap.add_argument("--report-dir", default=str(ROOT / "reports"))
    ap.add_argument("--min-orders", type=int, default=30, help="minimum orders for a seller or category to be ranked")
    ap.add_argument("--sample", action="store_true", help="use synthetic data (fake numbers) instead of real data")
    a = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)-8s %(message)s", datefmt="%H:%M:%S")
    log = logging.getLogger("pipeline")
    t0 = time.time()

    raw_dir = Path(a.raw_dir)
    min_orders = a.min_orders
    if a.sample:
        raw_dir = ROOT / "data" / "raw_sample"
        if not (raw_dir / "olist_orders_dataset.csv").exists():
            generate(raw_dir)
        min_orders = min(min_orders, 20)
        log.warning("SAMPLE MODE: numbers are synthetic and must not be used in a resume or report")

    try:
        engine = etl.run(raw_dir, a.db_url, Path(a.out_dir))
    except FileNotFoundError as e:
        raise SystemExit(f"\nERROR: {e}")
    metrics.run(engine, Path(a.out_dir), Path(a.report_dir), min_orders)
    log.info("done in %.1fs. Open %s", time.time() - t0, Path(a.report_dir) / "weekly_summary.md")


if __name__ == "__main__":
    main()
