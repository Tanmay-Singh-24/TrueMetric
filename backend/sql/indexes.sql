CREATE INDEX ON orders (order_purchase_timestamp);
CREATE INDEX ON orders (customer_id);
CREATE INDEX ON customers (customer_unique_id);
CREATE INDEX ON order_items (product_id);
CREATE INDEX ON order_reviews (order_id);
