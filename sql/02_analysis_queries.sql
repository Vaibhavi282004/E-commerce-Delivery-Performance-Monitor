-- Analysis queries for the Olist seller and customer experience project.
-- Portable SQL: tested on SQLite, written to also run on PostgreSQL.
-- Conventions: is_late = 1 means delivered after the estimated date.
--              delay_days > 0 means late, negative means early.
--              Delivery metrics only use delivered orders (is_delivered = 1).

-- ---------------------------------------------------------------------------
-- Q1. Headline KPIs
-- Business question: how healthy is the marketplace overall?
-- ---------------------------------------------------------------------------
SELECT
    COUNT(*)                                                         AS total_orders,
    SUM(is_delivered)                                                AS delivered_orders,
    ROUND(CAST(100.0 * SUM(CASE WHEN is_late = 0 THEN 1 ELSE 0 END)
               / SUM(is_delivered) AS NUMERIC), 2)                   AS on_time_pct,
    ROUND(CAST(AVG(review_score) AS NUMERIC), 2)                     AS avg_review_score,
    (SELECT ROUND(CAST(SUM(price) AS NUMERIC), 2) FROM fact_order_items) AS item_revenue
FROM fact_orders;

-- ---------------------------------------------------------------------------
-- Q2. Late-delivery rate by customer state, ranked
-- Business question: which regions get the worst delivery experience?
-- Skills: CTE, RANK window function
-- ---------------------------------------------------------------------------
WITH state_stats AS (
    SELECT c.state,
           COUNT(*) AS delivered_orders,
           100.0 * SUM(CASE WHEN f.is_late = 1 THEN 1 ELSE 0 END) / COUNT(*) AS late_pct,
           AVG(f.review_score) AS avg_review
    FROM fact_orders f
    JOIN dim_customer c ON c.customer_id = f.customer_id
    WHERE f.is_delivered = 1
    GROUP BY c.state
)
SELECT state,
       delivered_orders,
       ROUND(CAST(late_pct AS NUMERIC), 2)   AS late_pct,
       ROUND(CAST(avg_review AS NUMERIC), 2) AS avg_review,
       RANK() OVER (ORDER BY late_pct DESC)  AS late_rank
FROM state_stats
ORDER BY late_rank;

-- ---------------------------------------------------------------------------
-- Q3. Monthly late-delivery trend with month-over-month change
-- Business question: is delivery performance getting better or worse?
-- Skills: LAG window function
-- ---------------------------------------------------------------------------
WITH monthly AS (
    SELECT d.month_label,
           COUNT(*) AS delivered_orders,
           100.0 * SUM(CASE WHEN f.is_late = 1 THEN 1 ELSE 0 END) / COUNT(*) AS late_pct
    FROM fact_orders f
    JOIN dim_date d ON d.date_key = f.purchase_date
    WHERE f.is_delivered = 1
    GROUP BY d.month_label
)
SELECT month_label,
       delivered_orders,
       ROUND(CAST(late_pct AS NUMERIC), 2) AS late_pct,
       ROUND(CAST(late_pct - LAG(late_pct) OVER (ORDER BY month_label) AS NUMERIC), 2)
           AS change_vs_prev_month_pp
FROM monthly
ORDER BY month_label;

-- ---------------------------------------------------------------------------
-- Q4. Category performance: delay and satisfaction
-- Business question: which categories need operational attention?
-- Note: DISTINCT avoids double counting orders with two items of one category.
-- ---------------------------------------------------------------------------
WITH order_cat AS (
    SELECT DISTINCT i.order_id, p.category
    FROM fact_order_items i
    JOIN dim_product p ON p.product_id = i.product_id
)
SELECT oc.category,
       COUNT(*) AS delivered_orders,
       ROUND(CAST(100.0 * SUM(CASE WHEN f.is_late = 1 THEN 1 ELSE 0 END) / COUNT(*) AS NUMERIC), 2) AS late_pct,
       ROUND(CAST(AVG(f.review_score) AS NUMERIC), 2) AS avg_review
FROM order_cat oc
JOIN fact_orders f ON f.order_id = oc.order_id
WHERE f.is_delivered = 1
GROUP BY oc.category
HAVING COUNT(*) >= 30
ORDER BY late_pct DESC;

-- ---------------------------------------------------------------------------
-- Q5. Seller scorecard with late-rate deciles
-- Business question: which sellers should account managers look at first?
-- Skills: CTE chain, NTILE
-- ---------------------------------------------------------------------------
WITH seller_orders AS (
    SELECT DISTINCT i.seller_id, f.order_id, f.is_late, f.review_score
    FROM fact_order_items i
    JOIN fact_orders f ON f.order_id = i.order_id
    WHERE f.is_delivered = 1
),
seller_stats AS (
    SELECT seller_id,
           COUNT(*)       AS orders,
           SUM(is_late)   AS late_orders,
           100.0 * SUM(is_late) / COUNT(*) AS late_pct,
           AVG(review_score) AS avg_review
    FROM seller_orders
    GROUP BY seller_id
    HAVING COUNT(*) >= 30
)
SELECT seller_id,
       orders,
       late_orders,
       ROUND(CAST(late_pct AS NUMERIC), 2)   AS late_pct,
       ROUND(CAST(avg_review AS NUMERIC), 2) AS avg_review,
       NTILE(10) OVER (ORDER BY late_pct DESC) AS late_decile   -- 1 = worst 10%
FROM seller_stats
ORDER BY late_pct DESC;

-- ---------------------------------------------------------------------------
-- Q6. How concentrated is the lateness problem?
-- Business question: do a few sellers cause most late orders?
-- ---------------------------------------------------------------------------
WITH seller_orders AS (
    SELECT DISTINCT i.seller_id, f.order_id, f.is_late
    FROM fact_order_items i
    JOIN fact_orders f ON f.order_id = i.order_id
    WHERE f.is_delivered = 1
),
seller_stats AS (
    SELECT seller_id, COUNT(*) AS orders, SUM(is_late) AS late_orders,
           100.0 * SUM(is_late) / COUNT(*) AS late_pct
    FROM seller_orders
    GROUP BY seller_id
    HAVING COUNT(*) >= 30
),
ranked AS (
    SELECT *, NTILE(10) OVER (ORDER BY late_pct DESC) AS decile
    FROM seller_stats
)
SELECT decile,
       COUNT(*)           AS sellers,
       SUM(orders)        AS orders,
       SUM(late_orders)   AS late_orders,
       ROUND(CAST(100.0 * SUM(late_orders) / (SELECT SUM(late_orders) FROM seller_stats) AS NUMERIC), 2)
           AS share_of_all_late_orders_pct
FROM ranked
GROUP BY decile
ORDER BY decile;

-- ---------------------------------------------------------------------------
-- Q7. Review score by how late or early the order arrived
-- Business question: how much does lateness hurt customer satisfaction?
-- Skills: CASE WHEN bucketing
-- ---------------------------------------------------------------------------
SELECT CASE WHEN delay_days <= -7 THEN '1. 7+ days early'
            WHEN delay_days <= 0  THEN '2. on time (0-6 days early)'
            WHEN delay_days <= 3  THEN '3. 1-3 days late'
            WHEN delay_days <= 7  THEN '4. 4-7 days late'
            ELSE                       '5. 8+ days late' END AS delivery_bucket,
       COUNT(*) AS orders,
       ROUND(CAST(AVG(review_score) AS NUMERIC), 2) AS avg_review,
       ROUND(CAST(100.0 * SUM(CASE WHEN review_score = 1 THEN 1 ELSE 0 END) / COUNT(*) AS NUMERIC), 2)
           AS one_star_pct
FROM fact_orders
WHERE is_delivered = 1 AND review_score IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- ---------------------------------------------------------------------------
-- Q8. Revenue by category with cumulative share (Pareto)
-- Business question: which categories drive most of the revenue?
-- Skills: running total with window SUM
-- ---------------------------------------------------------------------------
WITH cat_rev AS (
    SELECT p.category, SUM(i.price) AS revenue
    FROM fact_order_items i
    JOIN dim_product p ON p.product_id = i.product_id
    GROUP BY p.category
)
SELECT category,
       ROUND(CAST(revenue AS NUMERIC), 2) AS revenue,
       ROUND(CAST(100.0 * revenue / SUM(revenue) OVER () AS NUMERIC), 2) AS share_pct,
       ROUND(CAST(100.0 * SUM(revenue) OVER (ORDER BY revenue DESC) / SUM(revenue) OVER () AS NUMERIC), 2)
           AS cumulative_share_pct
FROM cat_rev
ORDER BY revenue DESC;

-- ---------------------------------------------------------------------------
-- Q9. Repeat-customer rate
-- Business question: how many customers come back?
-- Note: customer_id is unique per order, customer_unique_id identifies a person.
-- ---------------------------------------------------------------------------
WITH cust_orders AS (
    SELECT c.customer_unique_id, COUNT(DISTINCT f.order_id) AS orders
    FROM fact_orders f
    JOIN dim_customer c ON c.customer_id = f.customer_id
    WHERE f.order_status <> 'canceled'
    GROUP BY c.customer_unique_id
)
SELECT COUNT(*) AS customers,
       SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END) AS repeat_customers,
       ROUND(CAST(100.0 * SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END) / COUNT(*) AS NUMERIC), 2) AS repeat_pct
FROM cust_orders;

-- ---------------------------------------------------------------------------
-- Q10. Seller late-rate spikes versus their own previous month
-- Business question: which sellers suddenly got worse (early-warning list)?
-- Skills: LAG with PARTITION BY
-- ---------------------------------------------------------------------------
WITH seller_month AS (
    SELECT i.seller_id,
           d.month_label,
           COUNT(DISTINCT f.order_id) AS orders,
           100.0 * COUNT(DISTINCT CASE WHEN f.is_late = 1 THEN f.order_id END)
                 / COUNT(DISTINCT f.order_id) AS late_pct
    FROM fact_order_items i
    JOIN fact_orders f ON f.order_id = i.order_id
    JOIN dim_date d    ON d.date_key = f.purchase_date
    WHERE f.is_delivered = 1
    GROUP BY i.seller_id, d.month_label
),
with_prev AS (
    SELECT *, LAG(late_pct) OVER (PARTITION BY seller_id ORDER BY month_label) AS prev_late_pct
    FROM seller_month
)
SELECT seller_id,
       month_label,
       orders,
       ROUND(CAST(late_pct AS NUMERIC), 2)                 AS late_pct,
       ROUND(CAST(prev_late_pct AS NUMERIC), 2)            AS prev_month_late_pct,
       ROUND(CAST(late_pct - prev_late_pct AS NUMERIC), 2) AS jump_pp
FROM with_prev
WHERE orders >= 5 AND late_pct - prev_late_pct >= 20
ORDER BY jump_pp DESC;

-- ---------------------------------------------------------------------------
-- Q11. Do holidays and weekends affect lateness?
-- Business question: should delivery promises change around holidays?
-- ---------------------------------------------------------------------------
SELECT d.is_holiday,
       d.is_weekend,
       COUNT(*) AS delivered_orders,
       ROUND(CAST(100.0 * SUM(CASE WHEN f.is_late = 1 THEN 1 ELSE 0 END) / COUNT(*) AS NUMERIC), 2) AS late_pct
FROM fact_orders f
JOIN dim_date d ON d.date_key = f.purchase_date
WHERE f.is_delivered = 1
GROUP BY d.is_holiday, d.is_weekend
ORDER BY d.is_holiday, d.is_weekend;

-- ---------------------------------------------------------------------------
-- Q12. Top 3 sellers by revenue in each seller state
-- Skills: ROW_NUMBER with PARTITION BY
-- ---------------------------------------------------------------------------
WITH seller_rev AS (
    SELECT s.state, i.seller_id, SUM(i.price) AS revenue
    FROM fact_order_items i
    JOIN dim_seller s ON s.seller_id = i.seller_id
    GROUP BY s.state, i.seller_id
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY state ORDER BY revenue DESC) AS rn
    FROM seller_rev
)
SELECT state, seller_id, ROUND(CAST(revenue AS NUMERIC), 2) AS revenue, rn AS rank_in_state
FROM ranked
WHERE rn <= 3
ORDER BY state, rn;

-- ---------------------------------------------------------------------------
-- Q13. Freight cost as a share of order value, by customer state
-- Business question: where does shipping cost eat the order?
-- ---------------------------------------------------------------------------
SELECT c.state,
       COUNT(*) AS orders,
       ROUND(CAST(100.0 * SUM(f.freight_value) / SUM(f.order_value) AS NUMERIC), 2) AS freight_pct_of_order_value
FROM fact_orders f
JOIN dim_customer c ON c.customer_id = f.customer_id
WHERE f.order_value > 0
GROUP BY c.state
ORDER BY freight_pct_of_order_value DESC;

-- ---------------------------------------------------------------------------
-- Q14. Impact estimate: what if the worst 10% of sellers matched everyone else?
-- Business question: how many late orders could a seller-improvement program avoid?
-- This is a what-if estimate, not a forecast. State that in your report.
-- ---------------------------------------------------------------------------
WITH seller_orders AS (
    SELECT DISTINCT i.seller_id, f.order_id, f.is_late
    FROM fact_order_items i
    JOIN fact_orders f ON f.order_id = i.order_id
    WHERE f.is_delivered = 1
),
seller_stats AS (
    SELECT seller_id, COUNT(*) AS orders, SUM(is_late) AS late_orders,
           100.0 * SUM(is_late) / COUNT(*) AS late_pct
    FROM seller_orders
    GROUP BY seller_id
    HAVING COUNT(*) >= 30
),
ranked AS (
    SELECT *, NTILE(10) OVER (ORDER BY late_pct DESC) AS decile
    FROM seller_stats
),
rest AS (
    SELECT 100.0 * SUM(late_orders) / SUM(orders) AS rest_late_pct
    FROM ranked WHERE decile > 1
)
SELECT SUM(w.orders)       AS worst_decile_orders,
       SUM(w.late_orders)  AS late_orders_now,
       ROUND(CAST(SUM(w.orders * r.rest_late_pct / 100.0) AS NUMERIC), 0) AS late_orders_if_fixed,
       ROUND(CAST(SUM(w.late_orders) - SUM(w.orders * r.rest_late_pct / 100.0) AS NUMERIC), 0)
           AS late_orders_avoided
FROM ranked w
CROSS JOIN rest r
WHERE w.decile = 1;
