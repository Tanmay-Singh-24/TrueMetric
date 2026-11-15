SELECT COUNT(*) AS orders
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
  AND o.order_purchase_timestamp >= %(start_date)s::date
  AND o.order_purchase_timestamp <  %(end_date)s::date + 1
  AND (%(state)s::text IS NULL OR c.customer_state = %(state)s::text)
