-- Purchase behavior analysis queries (SQLite)
-- Each block starts with "-- name: ..." so analysis.py can run it by name.
-- Revenue is counted from completed orders only.
-- Dates are text in YYYY-MM-DD form, so strftime() and julianday() are used for date math.


-- name: monthly_revenue
-- Revenue, order count and average order value per month.
SELECT strftime('%Y-%m-01', o.order_date)  AS month,
       COUNT(DISTINCT o.order_id)          AS orders,
       SUM(oi.quantity * oi.unit_price)    AS revenue,
       ROUND(SUM(oi.quantity * oi.unit_price) / COUNT(DISTINCT o.order_id), 2) AS avg_order_value
FROM orders o
JOIN order_items oi USING (order_id)
WHERE o.status = 'completed'
GROUP BY 1
ORDER BY 1;


-- name: top_products
-- Top 10 products by revenue, with a rank (window function).
SELECT RANK() OVER (ORDER BY SUM(oi.quantity * oi.unit_price) DESC) AS revenue_rank,
       p.product_name,
       c.category_name,
       SUM(oi.quantity)                 AS units_sold,
       SUM(oi.quantity * oi.unit_price) AS revenue
FROM order_items oi
JOIN orders o     USING (order_id)
JOIN products p   USING (product_id)
JOIN categories c USING (category_id)
WHERE o.status = 'completed'
GROUP BY p.product_id, p.product_name, c.category_name
ORDER BY revenue_rank
LIMIT 10;


-- name: category_share
-- Revenue per category and its share of total revenue.
SELECT c.category_name,
       SUM(oi.quantity * oi.unit_price) AS revenue,
       ROUND(100.0 * SUM(oi.quantity * oi.unit_price)
             / SUM(SUM(oi.quantity * oi.unit_price)) OVER (), 1) AS revenue_share_pct
FROM order_items oi
JOIN orders o     USING (order_id)
JOIN products p   USING (product_id)
JOIN categories c USING (category_id)
WHERE o.status = 'completed'
GROUP BY c.category_name
ORDER BY revenue DESC;


-- name: repeat_rate
-- Share of buyers who placed at least two completed orders.
WITH per_customer AS (
    SELECT customer_id, COUNT(*) AS completed_orders
    FROM orders
    WHERE status = 'completed'
    GROUP BY customer_id
)
SELECT COUNT(*)                                            AS buyers,
       COUNT(*) FILTER (WHERE completed_orders >= 2)       AS repeat_buyers,
       ROUND(100.0 * COUNT(*) FILTER (WHERE completed_orders >= 2) / COUNT(*), 1) AS repeat_rate_pct
FROM per_customer;


-- name: days_between_orders
-- Average and median number of days between a customer's consecutive orders.
-- SQLite has no median function, so the middle row(s) are picked with ROW_NUMBER.
WITH gaps AS (
    SELECT CAST(julianday(order_date)
                - julianday(LAG(order_date) OVER (PARTITION BY customer_id ORDER BY order_date, order_id))
                AS INTEGER) AS gap_days
    FROM orders
    WHERE status = 'completed'
),
ranked AS (
    SELECT gap_days,
           ROW_NUMBER() OVER (ORDER BY gap_days) AS rn,
           COUNT(*) OVER ()                      AS n
    FROM gaps
    WHERE gap_days IS NOT NULL
)
SELECT ROUND((SELECT AVG(gap_days) FROM ranked), 1) AS avg_days_between_orders,
       ROUND(AVG(gap_days), 1)                      AS median_days_between_orders
FROM ranked
WHERE rn IN ((n + 1) / 2, (n + 2) / 2);


-- name: rfm
-- RFM per customer: Recency (days since last order), Frequency (orders), Monetary (spend).
-- Each is scored 1-4 with NTILE, where 4 is best.
WITH ref AS (
    SELECT date(MAX(order_date), '+1 day') AS ref_date FROM orders WHERE status = 'completed'
),
totals AS (
    SELECT o.customer_id,
           MAX(o.order_date)                AS last_order,
           COUNT(DISTINCT o.order_id)       AS frequency,
           SUM(oi.quantity * oi.unit_price) AS monetary
    FROM orders o
    JOIN order_items oi USING (order_id)
    WHERE o.status = 'completed'
    GROUP BY o.customer_id
),
scored AS (
    SELECT t.customer_id,
           CAST(julianday(r.ref_date) - julianday(t.last_order) AS INTEGER) AS recency_days,
           t.frequency,
           t.monetary
    FROM totals t
    CROSS JOIN ref r
)
SELECT customer_id,
       recency_days,
       frequency,
       monetary,
       NTILE(4) OVER (ORDER BY recency_days DESC) AS r_score,
       NTILE(4) OVER (ORDER BY frequency)         AS f_score,
       NTILE(4) OVER (ORDER BY monetary)          AS m_score
FROM scored
ORDER BY customer_id;


-- name: bought_together
-- Product pairs that appear in the same completed order most often.
SELECT p1.product_name AS product_a,
       p2.product_name AS product_b,
       COUNT(*)        AS orders_together
FROM order_items a
JOIN order_items b ON a.order_id = b.order_id AND a.product_id < b.product_id
JOIN orders o      ON o.order_id = a.order_id AND o.status = 'completed'
JOIN products p1   ON p1.product_id = a.product_id
JOIN products p2   ON p2.product_id = b.product_id
GROUP BY p1.product_name, p2.product_name
ORDER BY orders_together DESC, product_a, product_b
LIMIT 10;


-- name: new_vs_returning
-- Customers per month, split into first-time and returning buyers.
WITH first_orders AS (
    SELECT customer_id, MIN(order_date) AS first_date
    FROM orders
    WHERE status = 'completed'
    GROUP BY customer_id
)
SELECT strftime('%Y-%m-01', o.order_date) AS month,
       COUNT(DISTINCT o.customer_id) FILTER (
           WHERE strftime('%Y-%m', o.order_date) = strftime('%Y-%m', f.first_date)) AS new_customers,
       COUNT(DISTINCT o.customer_id) FILTER (
           WHERE strftime('%Y-%m', o.order_date) > strftime('%Y-%m', f.first_date)) AS returning_customers
FROM orders o
JOIN first_orders f USING (customer_id)
WHERE o.status = 'completed'
GROUP BY 1
ORDER BY 1;
