SELECT ROUND(100.0 * COUNT(*) FILTER (
           WHERE o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date
       ) / NULLIF(COUNT(*), 0), 2) AS late_rate_pct,
       COUNT(*) FILTER (
           WHERE o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date
       ) AS late_orders,
       COUNT(*) AS delivered_orders
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
  AND o.order_purchase_timestamp >= %(start_date)s::date
  AND o.order_purchase_timestamp <  %(end_date)s::date + 1
  AND (%(state)s::text IS NULL OR c.customer_state = %(state)s::text)
