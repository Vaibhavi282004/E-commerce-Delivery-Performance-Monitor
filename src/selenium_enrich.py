"""OPTIONAL enrichment step: scrape Brazilian public holidays with Selenium.

Why: late deliveries may cluster around holidays. This gives dim_date an is_holiday flag
built from live web data instead of only the hand-typed fallback in data/reference/.

How it fits the pipeline:
    python -m src.selenium_enrich            # writes data/reference/brazil_holidays_scraped.csv
    python -m src.run_pipeline --sample      # etl.py automatically prefers the scraped file if it exists

IMPORTANT: this script has NOT been tested against the live website (the build sandbox has no
browser access). Page layouts change. If the selectors below stop matching, the script prints
a clear message, writes nothing, and the pipeline keeps using the fallback file.
Check the site's terms before scraping and keep the request volume tiny (3 pages here).

Needs: pip install selenium, plus Chrome installed (Selenium 4.6+ downloads the driver itself).
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reference" / "brazil_holidays_scraped.csv"
URL = "https://www.timeanddate.com/holidays/brazil/{year}"


def scrape_year(driver, year: int) -> list[tuple[str, str]]:
    from selenium.webdriver.common.by import By

    driver.get(URL.format(year=year))
    rows = driver.find_elements(By.CSS_SELECTOR, "table#holidays-table tbody tr")
    found = []
    for row in rows:
        cells = row.find_elements(By.CSS_SELECTOR, "th, td")
        if len(cells) < 3:
            continue
        date_text, name = cells[0].text.strip(), cells[2].text.strip()
        kind = cells[3].text.strip().lower() if len(cells) > 3 else ""
        if "national" not in kind:           # keep national holidays only
            continue
        try:
            parsed = datetime.strptime(f"{date_text} {year}", "%b %d %Y")
        except ValueError:
            continue
        found.append((parsed.strftime("%Y-%m-%d"), re.sub(r"\s+", " ", name)))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", nargs="+", type=int, default=[2016, 2017, 2018])
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    a = ap.parse_args()

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        print("selenium is not installed. Run: pip install selenium")
        return 1

    opts = Options()
    if not a.headed:
        opts.add_argument("--headless=new")
    driver = webdriver.Chrome(options=opts)
    try:
        holidays = [h for y in a.years for h in scrape_year(driver, y)]
    finally:
        driver.quit()

    if len(holidays) < 5 * len(a.years):
        print(f"Only {len(holidays)} holidays found, page layout probably changed. "
              "Nothing written, the pipeline will use data/reference/brazil_holidays.csv.")
        return 2

    df = pd.DataFrame(holidays, columns=["date", "holiday_name"]).drop_duplicates("date").sort_values("date")
    df.to_csv(OUT, index=False)
    print(f"Wrote {len(df)} holidays to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
