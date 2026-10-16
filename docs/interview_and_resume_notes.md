# Interview and Resume Notes for This Project

## Resume bullets (fill in YOUR real numbers, delete the brackets)
- Built an automated SQL-Python-Power BI pipeline on [N]k+ e-commerce orders (star schema, ETL, validation checks) to monitor delivery and seller performance.
- Found that late deliveries lowered average review scores by [G] points and that the worst 10% of sellers caused [S]% of late orders; recommended a seller corrective-action program with an estimated [N] late orders avoided.
- Automated weekly reporting with Python and an Excel VBA macro, removing manual report preparation.

Only claim tools you actually used. Say "PostgreSQL/SQLite" and "Power BI", not Redshift or QuickSight, unless you used them.

## 60-second project pitch
"I wanted a project that looks like real analyst work, so I took a marketplace dataset and asked: why do orders arrive late, and what does it cost in customer satisfaction? I modelled it as a star schema, wrote SQL for the metrics, used Python for the ETL and the statistics, and built a three-page Power BI dashboard. The main finding was [finding]. I recommended [action] and estimated [impact], and I automated the weekly report so a leader could track it without me."

## Questions you should be ready for
1. **Why a star schema?** Facts (orders, items) hold measurable events, dimensions hold descriptive attributes. It makes joins simple and metrics consistent.
2. **Why two fact tables?** Different grain. An order can contain items from several sellers, so seller metrics must come from the item grain.
3. **How did you define "late"?** Delivered date later than the estimated date, at date level. Only delivered orders count.
4. **How do you know the late-vs-review link is real?** Compared means, ran a Welch t-test, and looked at review scores by lateness bucket. It is association; product quality also matters.
5. **What would you do with more time?** Add carrier and distance, forecast late rate, set up alerts.
6. **What are the limits of your impact estimate?** It assumes Red sellers can reach everyone else's late rate. It is a what-if, not a forecast.
7. **Tell me about a data quality problem you found.** Prepare a real one from the real data: nulls in delivered dates, multiple reviews per order, orders with several sellers.

## Leadership Principles stories to prepare (STAR format)
Write 5 or 6 stories from this project and your studies:
- **Dive Deep:** how you investigated the seller concentration or the data quality issue.
- **Customer Obsession:** tying delivery metrics to the customer's review experience.
- **Ownership:** building the whole pipeline end to end.
- **Invent and Simplify:** automating the weekly report.
- **Are Right, A Lot:** how you checked SQL results against Python results.
- **Deliver Results:** the recommendation and its estimated impact.

## SQL practice list (from the queries in this repo)
Be able to write these from scratch: GROUP BY with HAVING, multi-table JOINs, CTEs, RANK / ROW_NUMBER / NTILE, LAG for month-over-month, CASE WHEN bucketing, running totals with SUM() OVER, and counting distinct customers for repeat rate.
