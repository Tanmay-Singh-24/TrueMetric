SELECT p.category,
       SUM(oi.price) AS revenue,
       COUNT(*) AS units
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN customers c    ON c.customer_id = o.customer_id
JOIN products p     ON p.product_id = oi.product_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
  AND o.order_purchase_timestamp >= %(start_date)s::date
  AND o.order_purchase_timestamp <  %(end_date)s::date + 1
  AND (%(state)s::text IS NULL OR c.customer_state = %(state)s::text)
GROUP BY p.category
ORDER BY units DESC, p.category
LIMIT %(top_n)s::int
