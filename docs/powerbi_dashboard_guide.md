# Power BI Dashboard Guide (3 pages)

Build the dashboard from the CSVs in `data/processed/` (run the pipeline first).
Tableau works the same way. Amazon's listing accepts "Power BI or other BI packages".

## 1. Load the data
Home > Get data > Text/CSV, load these:

| File | Purpose |
|---|---|
| `fact_orders.csv` | one row per order: delivery and review metrics |
| `fact_order_items.csv` | one row per item: seller, product, price |
| `dim_customer.csv`, `dim_seller.csv`, `dim_product.csv`, `dim_date.csv` | dimensions |
| `seller_scorecard.csv` | seller-level late rate, tier, anomaly flag (precomputed) |
| `monthly_trend.csv`, `delivery_by_state.csv`, `category_performance.csv` | optional, for quick visuals |

In Power Query set data types: `purchase_date` and `dim_date[date_key]` to **Date**, numeric columns to Decimal or Whole number.

## 2. Model (Model view)
```
dim_date[date_key]        1 ──► *  fact_orders[purchase_date]
dim_customer[customer_id] 1 ──► *  fact_orders[customer_id]
fact_orders[order_id]     1 ──► *  fact_order_items[order_id]
dim_seller[seller_id]     1 ──► *  fact_order_items[seller_id]
dim_product[product_id]   1 ──► *  fact_order_items[product_id]
dim_seller[seller_id]     1 ──► 1  seller_scorecard[seller_id]
```
Keep every relationship single-direction (dimension filters fact).

**Trap to avoid:** an order can have items from more than one seller. Computing seller on-time % by filtering `fact_orders` through `fact_order_items` double counts. Use the precomputed `seller_scorecard` table for seller metrics.

## 3. Measures (DAX)
These were written from the schema but not run in Power BI by the author. Test each one against the matching SQL query (Q1, Q9) and fix small syntax issues.

```dax
Total Orders      = DISTINCTCOUNT ( fact_orders[order_id] )
Delivered Orders  = CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[is_delivered] = 1 )
Late Orders       = CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[is_late] = 1 )
On-Time %         = DIVIDE ( [Delivered Orders] - [Late Orders], [Delivered Orders] )
Late %            = 1 - [On-Time %]
Avg Review        = AVERAGE ( fact_orders[review_score] )
Revenue           = SUM ( fact_order_items[price] )
Avg Delivery Days = CALCULATE ( AVERAGE ( fact_orders[delivery_days] ), fact_orders[is_delivered] = 1 )
Unique Customers  = DISTINCTCOUNT ( dim_customer[customer_unique_id] )
Repeat Customers  =
    COUNTROWS (
        FILTER (
            VALUES ( dim_customer[customer_unique_id] ),
            CALCULATE ( DISTINCTCOUNT ( fact_orders[order_id] ) ) > 1
        )
    )
Repeat Customer % = DIVIDE ( [Repeat Customers], [Unique Customers] )
```
Format percentage measures as % with 1 decimal.

## 4. Page layout

### Page 1: Executive overview ("how are we doing?")
- Top row of 5 KPI cards: Total Orders, Revenue, On-Time %, Avg Review, Repeat Customer %.
- Line chart: `monthly_trend[late_pct]` by `month_label`, so leaders see the trend.
- Column chart: Avg Review by delivery bucket (from `delay_vs_review.csv`). This is the "so what" visual: lateness destroys satisfaction.
- Slicers: Year, Customer state.
- Title it with the finding, for example "Late deliveries cut average review by X points" (fill X from your real results).

### Page 2: Seller scorecard ("who needs attention?")
- Table from `seller_scorecard`: seller_id, orders, late_pct, avg_review, revenue, tier. Sort by late_pct descending.
- Conditional formatting: tier Red/Amber/Green background, data bars on late_pct.
- Scatter: x = late_pct, y = avg_review, size = orders, colour = tier.
- Cards: number of Red sellers and share of all late orders they cause (from `reports/analysis_summary.json`).
- Slicer: tier, seller state.

### Page 3: Delivery and category deep-dive ("where and why?")
- Filled map or bar chart: late % by customer state.
- Bar chart: late % by product category (min orders applied).
- Matrix: category x month heat map of late %.
- Optional: holiday vs non-holiday late % (Q11).

## 5. Make it recruiter-ready
- Use one colour for "good" and one for "bad", consistently across pages.
- Every chart gets a title that states a finding, not a label.
- Add a tooltip or text box on each page: "What to do with this".
- Export screenshots to `docs/screenshots/` and publish to the web (or record a 2-minute screen video) so a recruiter can see it without opening Power BI.
