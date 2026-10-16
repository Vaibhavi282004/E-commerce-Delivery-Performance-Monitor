# Seller & Customer Experience Analytics (Olist E-commerce)

> **Business question:** Which sellers, regions and categories hurt customer experience through late deliveries, how much does it cost in review scores, and how can a leader monitor it automatically every week?

An end-to-end analyst project: **SQL star schema, Python ETL and statistics, automated reporting (Python + Excel VBA), Power BI dashboard, and a written business memo.** It mirrors the work in Amazon Business Analyst listings: owning reports, dashboards and automation that improve customer and selling-partner experience.

## Key findings
> Fill this in after running on the REAL data. Keep it to 4 or 5 lines with real numbers.
> Example shape: "Late orders score 2.x stars vs 4.x on time. The worst 10% of sellers cause ~X% of late orders. Region Y has the highest late rate (Z%)."

- [finding 1]
- [finding 2]
- [finding 3]

Dashboard screenshots: `docs/screenshots/` (add yours). Business memo: `docs/business_memo.md` (copy and fill the template).

## Architecture
```
Olist CSVs (8 files)
   │  src/etl.py        clean, validate, build star schema
   ▼
SQLite or PostgreSQL warehouse
   fact_orders (order grain)   fact_order_items (item grain)   fact_reviews
   dim_date  dim_customer  dim_seller  dim_product
   │                          │
   │ sql/02_analysis_queries  │ src/metrics.py: KPIs, seller scorecard (Red/Amber/Green),
   │ 14 interview-style       │ anomaly flags, t-test, review-text keywords, what-if impact
   ▼                          ▼
data/processed/*.csv  ──►  Power BI dashboard (docs/powerbi_dashboard_guide.md)
reports/weekly_summary.md  +  vba/WeeklyReport.bas  ──►  formatted Excel weekly report
```

## Quick start
```bash
# 1. setup (Python 3.10+)
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install pandas numpy scipy pytest

# 2. try it on synthetic data first (numbers are FAKE, for checking your setup only)
python -m src.run_pipeline --sample

# 3. run on the real data
#    Download "Brazilian E-Commerce Public Dataset by Olist" from Kaggle,
#    unzip the 8 CSV files into data/raw/
python -m src.run_pipeline --raw-dir data/raw

# 4. look at the results
#    reports/weekly_summary.md, reports/analysis_summary.json, data/processed/*.csv
```
Open `data/processed/olist_dw.db` with DB Browser for SQLite (free) and paste queries from `sql/02_analysis_queries.sql`.

Optional: PostgreSQL (`pip install sqlalchemy psycopg2-binary`, then `--db-url postgresql+psycopg2://user:pw@localhost:5432/olist`).

## What is in the repo
| Path | What it is |
|---|---|
| `sql/01_schema.sql` | star schema DDL |
| `sql/02_analysis_queries.sql` | 14 business queries: CTEs, RANK, NTILE, LAG, CASE WHEN, running totals |
| `src/etl.py` | extract, clean, validate, load |
| `src/metrics.py` | KPIs, seller tiers, anomaly flags, Welch t-test, review keywords, what-if estimate |
| `src/run_pipeline.py` | one command to run everything |
| `src/make_sample_data.py` | synthetic data generator for testing |
| `src/selenium_enrich.py` | optional: scrape Brazilian holidays into `dim_date` |
| `vba/WeeklyReport.bas` | Excel macro that builds a formatted weekly workbook |
| `tests/test_pipeline.py` | end-to-end consistency tests |
| `docs/` | Power BI guide, memo template, interview and resume notes |

## Method notes
- **Late** = delivered date after the estimated date (date level). Only delivered orders count in delivery metrics.
- **Two fact tables** because one order can contain items from several sellers. Seller metrics use distinct (order, seller) pairs.
- **Seller tiers:** among sellers with at least `--min-orders` orders (default 30), Red = top 10% by late rate and above the overall rate, Amber = top 30%, otherwise Green. Smaller sellers are marked "Insufficient data".
- **Anomaly flag:** seller late rate more than 2 standard deviations above the seller average.
- **What-if estimate:** how many late orders would disappear if Red sellers matched everyone else. An estimate, not a forecast.
- Review text is Portuguese, so keyword analysis uses a small Portuguese stopword list.

## Status: what was and was not verified
Verified by the author on synthetic data (Python 3.13, pandas 3, SQLite):
- Full pipeline runs end to end; all 14 SQL queries execute on SQLite; SQL and Python agree on on-time % and repeat-customer %.
- Planted "bad sellers" in the synthetic data are recovered in the Red tier.

**Not verified** (no access in the build environment): the real Olist data, PostgreSQL, the Selenium scraper against the live site, the VBA macro in Excel, the DAX measures in Power BI, and `pytest` itself (run `python tests/test_pipeline.py` or `python -m pytest -q` on your machine). Expect to fix small issues there.

## Limitations
- Olist data is 2016 to 2018 and Brazilian, so findings are an exercise, not Amazon India facts.
- Seller late rate is not adjusted for distance, product weight or carrier.
- Late-vs-review is an association, not proof of cause.

## Data source
Olist Brazilian E-Commerce Public Dataset (Kaggle), CC BY-NC-SA 4.0. Raw data is not included in this repo.
