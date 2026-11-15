SELECT ROUND(AVG(r.review_score), 2) AS average_score,
       COUNT(*) AS reviews
FROM order_reviews r
JOIN orders o ON o.order_id = r.order_id
WHERE o.order_purchase_timestamp >= %(start_date)s::date
  AND o.order_purchase_timestamp <  %(end_date)s::date + 1
  AND (%(category)s::text IS NULL OR EXISTS (
        SELECT 1
        FROM order_items oi
        JOIN products p ON p.product_id = oi.product_id
        WHERE oi.order_id = o.order_id
          AND p.category = %(category)s::text
      ))
