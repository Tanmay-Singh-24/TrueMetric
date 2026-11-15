WITH customer_orders AS (
    SELECT c.customer_unique_id, COUNT(*) AS orders
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
      AND o.order_purchase_timestamp >= %(start_date)s::date
      AND o.order_purchase_timestamp <  %(end_date)s::date + 1
    GROUP BY c.customer_unique_id
)
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE orders >= 2) / NULLIF(COUNT(*), 0), 2) AS repeat_rate_pct,
       COUNT(*) FILTER (WHERE orders >= 2) AS repeat_customers,
       COUNT(*) AS customers
FROM customer_orders
