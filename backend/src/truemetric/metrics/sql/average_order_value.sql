SELECT ROUND(SUM(oi.price) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2) AS average_order_value,
       COUNT(DISTINCT o.order_id) AS orders
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN customers c    ON c.customer_id = o.customer_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
  AND o.order_purchase_timestamp >= %(start_date)s::date
  AND o.order_purchase_timestamp <  %(end_date)s::date + 1
  AND (%(state)s::text IS NULL OR c.customer_state = %(state)s::text)
