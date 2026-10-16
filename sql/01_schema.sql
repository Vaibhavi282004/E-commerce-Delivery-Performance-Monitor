-- Star schema for the Olist seller and customer experience warehouse.
-- Written in plain ANSI-style SQL so it runs on SQLite (default) and PostgreSQL.
-- Dates are stored as ISO text (YYYY-MM-DD). Booleans are 0/1 integers.

DROP TABLE IF EXISTS fact_reviews;
DROP TABLE IF EXISTS fact_order_items;
DROP TABLE IF EXISTS fact_orders;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_seller;
DROP TABLE IF EXISTS dim_product;

CREATE TABLE dim_date (
    date_key      TEXT PRIMARY KEY,
    year          INTEGER,
    month         INTEGER,
    month_label   TEXT,
    quarter       INTEGER,
    day_of_week   TEXT,
    is_weekend    INTEGER,
    is_holiday    INTEGER,
    holiday_name  TEXT
);

CREATE TABLE dim_customer (
    customer_id         TEXT PRIMARY KEY,
    customer_unique_id  TEXT,
    city                TEXT,
    state               TEXT
);

CREATE TABLE dim_seller (
    seller_id  TEXT PRIMARY KEY,
    city       TEXT,
    state      TEXT
);

CREATE TABLE dim_product (
    product_id   TEXT PRIMARY KEY,
    category     TEXT,
    weight_g     DOUBLE PRECISION,
    photos_qty   INTEGER
);

-- Grain: one row per order
CREATE TABLE fact_orders (
    order_id        TEXT PRIMARY KEY,
    customer_id     TEXT,
    purchase_date   TEXT,
    order_status    TEXT,
    delivered_date  TEXT,
    estimated_date  TEXT,
    delivery_days   DOUBLE PRECISION,
    estimated_days  DOUBLE PRECISION,
    delay_days      INTEGER,
    is_delivered    INTEGER,
    is_late         INTEGER,
    review_score    INTEGER,
    items_count     INTEGER,
    order_value     DOUBLE PRECISION,
    freight_value   DOUBLE PRECISION,
    payment_value   DOUBLE PRECISION
);

-- Grain: one row per order item (this is where the seller lives)
CREATE TABLE fact_order_items (
    order_id       TEXT,
    order_item_id  INTEGER,
    product_id     TEXT,
    seller_id      TEXT,
    price          DOUBLE PRECISION,
    freight_value  DOUBLE PRECISION
);

-- Grain: one row per review (used for text analysis)
CREATE TABLE fact_reviews (
    review_id        TEXT,
    order_id         TEXT,
    review_score     INTEGER,
    comment_title    TEXT,
    comment_message  TEXT,
    created_date     TEXT
);

CREATE INDEX idx_orders_purchase  ON fact_orders (purchase_date);
CREATE INDEX idx_orders_customer  ON fact_orders (customer_id);
CREATE INDEX idx_items_order      ON fact_order_items (order_id);
CREATE INDEX idx_items_seller     ON fact_order_items (seller_id);
CREATE INDEX idx_items_product    ON fact_order_items (product_id);
CREATE INDEX idx_reviews_order    ON fact_reviews (order_id);
