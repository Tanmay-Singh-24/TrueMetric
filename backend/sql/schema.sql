-- One row per ORDER, not per person. A returning buyer gets a new customer_id each time.
CREATE TABLE customers (
    customer_id        text PRIMARY KEY,  -- key used by orders; unique per order
    customer_unique_id text NOT NULL,     -- the actual person; use this to count customers
    customer_city      text NOT NULL,
    customer_state     text NOT NULL      -- two-letter Brazilian state code, e.g. 'SP'
);

CREATE TABLE sellers (
    seller_id    text PRIMARY KEY,
    seller_city  text NOT NULL,
    seller_state text NOT NULL            -- two-letter Brazilian state code
);

CREATE TABLE products (
    product_id       text PRIMARY KEY,
    category         text NOT NULL,       -- English category name, e.g. 'health_beauty'; 'unknown' if missing
    product_weight_g integer
);

CREATE TABLE orders (
    order_id                      text PRIMARY KEY,
    customer_id                   text NOT NULL REFERENCES customers,
    order_status                  text NOT NULL,       -- delivered, shipped, canceled, unavailable, invoiced, processing, created, approved
    order_purchase_timestamp      timestamp NOT NULL,  -- when the order was placed; use this for date filters
    order_approved_at             timestamp,
    order_delivered_carrier_date  timestamp,
    order_delivered_customer_date timestamp,           -- NULL if not delivered yet
    order_estimated_delivery_date timestamp NOT NULL   -- promised delivery date, always at midnight
);

-- One row per UNIT sold. An order with 3 units has 3 rows.
CREATE TABLE order_items (
    order_id      text NOT NULL REFERENCES orders,
    order_item_id integer NOT NULL,       -- 1, 2, 3... within the order
    product_id    text NOT NULL REFERENCES products,
    seller_id     text NOT NULL REFERENCES sellers,
    price         numeric(10,2) NOT NULL, -- item price in BRL, excluding freight
    freight_value numeric(10,2) NOT NULL, -- shipping charge for this item in BRL
    PRIMARY KEY (order_id, order_item_id)
);

-- One row per payment. An order can have several (e.g. voucher + credit card).
-- Never join this to order_items in the same query: both have many rows per order.
CREATE TABLE order_payments (
    order_id             text NOT NULL REFERENCES orders,
    payment_sequential   integer NOT NULL,
    payment_type         text NOT NULL,   -- credit_card, boleto, voucher, debit_card, not_defined
    payment_installments integer NOT NULL,
    payment_value        numeric(10,2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);

-- An order can have more than one review.
CREATE TABLE order_reviews (
    review_id            text NOT NULL,
    order_id             text NOT NULL REFERENCES orders,
    review_score         integer NOT NULL, -- 1 (worst) to 5 (best)
    review_creation_date timestamp NOT NULL,
    PRIMARY KEY (review_id, order_id)
);
