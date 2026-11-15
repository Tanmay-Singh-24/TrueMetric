# TrueMetric — Metric definitions

The ten verified metrics. Each has one definition, one SQL file and reference values to
check it against. **Do not change a definition or its SQL without asking** — every number
in the eval and the README depends on them. If a SQL result disagrees with a reference
value, stop and report the difference; do not adjust either side to make them match.

## Shared definitions

| Term | Definition |
|---|---|
| Valid order | `order_status NOT IN ('canceled', 'unavailable')` |
| Order date | `order_purchase_timestamp` |
| Date range | Both ends inclusive, by calendar day: `>= start_date` and `< end_date + 1 day` |
| Customer | `customer_unique_id`, never `customer_id` |
| Unit | One row in `order_items` |
| Revenue | Sum of `order_items.price`. Freight is excluded |
| Currency | Brazilian real (BRL), shown as `R$` |

When dates are not given, the range defaults to the data window, 2016-09-04 to
2018-10-17. Code resolves the defaults, so SQL always receives concrete dates.

## Catalogue

| id | Name | Arguments | Unit | Headline column |
|---|---|---|---|---|
| `merchandise_revenue` | Merchandise revenue | dates, state, category | brl | `revenue` |
| `order_count` | Number of orders | dates, state | count | `orders` |
| `average_order_value` | Average order value | dates, state | brl | `average_order_value` |
| `monthly_revenue` | Revenue by month | dates, state, category | table | — |
| `top_categories_by_revenue` | Top categories by revenue | dates, state, top_n | table | — |
| `top_categories_by_units` | Top categories by units sold | dates, state, top_n | table | — |
| `revenue_by_state` | Revenue by customer state | dates, top_n | table | — |
| `repeat_customer_rate` | Repeat customer rate | dates | percent | `repeat_rate_pct` |
| `late_delivery_rate` | Late delivery rate | dates, state | percent | `late_rate_pct` |
| `average_review_score` | Average review score | dates, category | score | `average_score` |

"dates" means `start_date` and `end_date`. `state` filters by the customer's state.

## SQL conventions

- Placeholders are psycopg named parameters. **Cast every placeholder**
  (`%(state)s::text`, `%(start_date)s::date`, `%(top_n)s::int`): psycopg 3 binds on the
  server, and an uncast placeholder that is NULL has no type.
- An optional filter is `(%(x)s::text IS NULL OR column = %(x)s::text)`.
- Each file is complete on its own. The shared `WHERE` lines are repeated in every file
  on purpose: a metric can then be read and verified without opening anything else.
- No literal `%` in the SQL (psycopg would read it as a placeholder).
- Pass only the arguments the metric declares.

---

## 1. `merchandise_revenue`

**Definition:** Total item price of valid orders placed in the date range. Freight is
excluded.
**Synonyms:** sales, revenue, GMV, merchandise value, turnover
**Audit notes:** "Item prices only; freight excluded" · "Excludes canceled and
unavailable orders" · "Dated by purchase time"

```sql
SELECT COALESCE(SUM(oi.price), 0) AS revenue,
       COUNT(DISTINCT o.order_id) AS orders
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN customers c    ON c.customer_id = o.customer_id
JOIN products p     ON p.product_id = oi.product_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
  AND o.order_purchase_timestamp >= %(start_date)s::date
  AND o.order_purchase_timestamp <  %(end_date)s::date + 1
  AND (%(state)s::text IS NULL OR c.customer_state = %(state)s::text)
  AND (%(category)s::text IS NULL OR p.category = %(category)s::text)
```

No row multiplication: the grain is the item row; each item has one order, one customer
and one product.

## 2. `order_count`

**Definition:** Number of valid orders placed in the date range.
**Synonyms:** orders, number of orders, order volume, how many orders
**Audit notes:** "Excludes canceled and unavailable orders" · "Counts orders, not items"

```sql
SELECT COUNT(*) AS orders
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
  AND o.order_purchase_timestamp >= %(start_date)s::date
  AND o.order_purchase_timestamp <  %(end_date)s::date + 1
  AND (%(state)s::text IS NULL OR c.customer_state = %(state)s::text)
```

## 3. `average_order_value`

**Definition:** Merchandise revenue divided by the number of valid orders that have at
least one item.
**Synonyms:** AOV, average basket, average order size, average spend per order
**Audit notes:** "Revenue ÷ orders, not the average item price" · "Item prices only;
freight excluded" · "Excludes canceled and unavailable orders"

```sql
SELECT ROUND(SUM(oi.price) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2) AS average_order_value,
       COUNT(DISTINCT o.order_id) AS orders
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN customers c    ON c.customer_id = o.customer_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
  AND o.order_purchase_timestamp >= %(start_date)s::date
  AND o.order_purchase_timestamp <  %(end_date)s::date + 1
  AND (%(state)s::text IS NULL OR c.customer_state = %(state)s::text)
```

The classic mistake this metric prevents is `AVG(price)`, which is the average item
price.

## 4. `monthly_revenue`

**Definition:** Merchandise revenue and order count for each calendar month in the date
range.
**Synonyms:** revenue trend, sales over time, monthly sales, revenue by month
**Audit notes:** same three as `merchandise_revenue`

```sql
SELECT date_trunc('month', o.order_purchase_timestamp)::date AS month,
       SUM(oi.price) AS revenue,
       COUNT(DISTINCT o.order_id) AS orders
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN customers c    ON c.customer_id = o.customer_id
JOIN products p     ON p.product_id = oi.product_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
  AND o.order_purchase_timestamp >= %(start_date)s::date
  AND o.order_purchase_timestamp <  %(end_date)s::date + 1
  AND (%(state)s::text IS NULL OR c.customer_state = %(state)s::text)
  AND (%(category)s::text IS NULL OR p.category = %(category)s::text)
GROUP BY 1
ORDER BY 1
```

## 5. `top_categories_by_revenue`

**Definition:** Product categories ranked by merchandise revenue.
**Synonyms:** best-selling categories by value, highest-revenue categories
**Audit notes:** "Ranked by item price total; freight excluded" · "Excludes canceled and
unavailable orders"

```sql
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
ORDER BY revenue DESC, p.category
LIMIT %(top_n)s::int
```

## 6. `top_categories_by_units`

**Definition:** Product categories ranked by number of units sold.
**Synonyms:** most-sold categories, best-selling categories by volume, most popular
categories
**Audit notes:** "Ranked by units (item rows), not revenue" · "Excludes canceled and
unavailable orders"

Same SQL as metric 5 with `ORDER BY units DESC, p.category`.

Metrics 5 and 6 are the standard `clarify` pair: "best-selling categories" could mean
either, and they give different answers (see the reference values).

## 7. `revenue_by_state`

**Definition:** Customer states ranked by merchandise revenue.
**Synonyms:** sales by state, top states, revenue by region
**Audit notes:** "State is the customer's state, not the seller's" · "Item prices only;
freight excluded" · "Excludes canceled and unavailable orders"

```sql
SELECT c.customer_state AS state,
       SUM(oi.price) AS revenue,
       COUNT(DISTINCT o.order_id) AS orders
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN customers c    ON c.customer_id = o.customer_id
WHERE o.order_status NOT IN ('canceled', 'unavailable')
  AND o.order_purchase_timestamp >= %(start_date)s::date
  AND o.order_purchase_timestamp <  %(end_date)s::date + 1
GROUP BY c.customer_state
ORDER BY revenue DESC, c.customer_state
LIMIT %(top_n)s::int
```

## 8. `repeat_customer_rate`

**Definition:** Of the customers who placed at least one valid order in the date range,
the percentage who placed two or more.
**Synonyms:** repeat purchase rate, returning customers, customer retention, loyalty
**Audit notes:** "A customer is a customer_unique_id" · "Only orders inside the date
range are counted" · "Excludes canceled and unavailable orders"

```sql
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
```

Grouping by `customer_id` instead would give 0%: every order has its own `customer_id`.

## 9. `late_delivery_rate`

**Definition:** Of delivered orders placed in the date range, the percentage delivered on
a later calendar day than the estimated delivery date.
**Synonyms:** late orders, delayed deliveries, on-time delivery (the complement),
delivery performance
**Audit notes:** "Delivered orders with a delivery date only" · "Late means delivered on
a later calendar day than promised" · "Dated by purchase time"

```sql
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
```

Dates are compared by calendar day because the estimated date is always stored at
midnight; comparing timestamps would count a delivery at 3 pm on the promised day as
late.

## 10. `average_review_score`

**Definition:** Average review score (1–5) of reviews on orders placed in the date range.
With a category, only orders containing at least one item of that category.
**Synonyms:** customer rating, satisfaction score, average rating, review average
**Audit notes:** "Every review counts once" · "All order statuses included" · "Dated by
the order's purchase time, not the review date"

```sql
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
```

`EXISTS` instead of a join: joining `order_items` would count a review once per item and
weight large orders more heavily.

---

## Reference values

Computed on 2026-11-15 from the raw CSV files with a pure-Python script (no SQL), using
the definitions above. `scripts/reference_values.py` must reproduce every number here
from the raw files, and the metric SQL must then match the script's output. Money
tolerance is 0.01.

### Single-value metrics

| Metric | All data | 2017 | 2018 |
|---|---|---|---|
| `merchandise_revenue` | 13,494,400.74 (98,199 orders) | 6,108,492.27 (44,375) | 7,341,182.41 (53,531) |
| `order_count` | 98,207 | 44,379 | 53,532 |
| `average_order_value` | 137.42 | 137.66 | 137.14 |
| `repeat_customer_rate` | 3.04% (2,888 of 94,990) | 2.83% (1,220 of 43,034) | 2.12% (1,110 of 52,337) |
| `late_delivery_rate` | 6.77% (6,534 of 96,470) | 5.65% (2,453 of 43,426) | 7.73% (4,078 of 52,777) |
| `average_review_score` | 4.09 (99,224 reviews) | 4.09 (45,044) | 4.09 (53,854) |

"All data" is 2016-09-04 to 2018-10-17. "2017" and "2018" are 1 January to 31 December.

### Table metrics, all data, top 5

`top_categories_by_revenue`

| category | revenue | units |
|---|---|---|
| health_beauty | 1,255,695.13 | 9,634 |
| watches_gifts | 1,198,185.21 | 5,970 |
| bed_bath_table | 1,035,964.06 | 11,097 |
| sports_leisure | 979,740.92 | 8,590 |
| computers_accessories | 904,322.02 | 7,781 |

`top_categories_by_units`

| category | units | revenue |
|---|---|---|
| bed_bath_table | 11,097 | 1,035,964.06 |
| health_beauty | 9,634 | 1,255,695.13 |
| sports_leisure | 8,590 | 979,740.92 |
| furniture_decor | 8,298 | 727,465.05 |
| computers_accessories | 7,781 | 904,322.02 |

`revenue_by_state`

| state | revenue |
|---|---|
| SP | 5,163,867.22 |
| RJ | 1,811,623.42 |
| MG | 1,573,508.20 |
| RS | 742,559.78 |
| PR | 676,883.06 |

`monthly_revenue`, selected months

| month | revenue | orders |
|---|---|---|
| 2017-01 | 120,098.27 | 787 |
| 2017-11 | 1,003,862.14 | 7,421 |
| 2017-12 | 742,183.79 | 5,618 |
| 2018-01 | 945,456.29 | 7,187 |
| 2018-08 | 848,860.10 | 6,421 |

### Filtered spot checks

| Check | Value |
|---|---|
| `merchandise_revenue`, 2018, state = SP | 2,960,471.25 |
| `merchandise_revenue`, 2017, category = health_beauty | 481,142.73 |
| `average_review_score`, all data, category = health_beauty | 4.18 (8,826 reviews) |

### The row-multiplication trap, measured

| Quantity (valid orders, all data) | Value |
|---|---|
| True total of `payment_value` | 15,739,137.01 |
| Same sum after joining `order_items` | 20,156,175.58 |
| Total freight | 2,245,816.19 |

Use the first two numbers in the README to show what the metric layer protects against.

---

## Known limits of these definitions

State these in the README; they are fair interview questions.

- "Revenue" is item price, not money received. Vouchers, instalment interest and freight
  are not in it.
- A valid order may still be undelivered (shipped, invoiced, processing).
- `repeat_customer_rate` only sees orders inside the chosen range, so a short range gives
  a lower rate.
- `average_order_value` and `order_count` use slightly different order sets: 8 valid
  orders have no item rows.
- Months outside 2017-01 to 2018-08 hold almost no orders, so trends at the edges of the
  data are not meaningful.
