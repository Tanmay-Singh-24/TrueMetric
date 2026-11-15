"""The ten verified metrics. Definitions and notes are copied from docs/METRICS.md."""

from dataclasses import dataclass
from typing import Literal

ArgName = Literal["start_date", "end_date", "state", "category", "top_n"]
DATES: frozenset[ArgName] = frozenset({"start_date", "end_date"})

VALID_ORDERS = "Excludes canceled and unavailable orders"
ITEM_PRICES_ONLY = "Item prices only; freight excluded"
DATED_BY_PURCHASE = "Dated by purchase time"


@dataclass(frozen=True)
class Metric:
    id: str  # also the name of the .sql file
    name: str
    definition: str  # one sentence; shown to the router and the user
    synonyms: tuple[str, ...]
    args: frozenset[ArgName]  # which arguments this metric accepts
    notes: tuple[str, ...]  # inclusion/exclusion lines for the audit panel
    unit: Literal["brl", "percent", "count", "score", "table"]
    value_column: str | None  # column holding the headline value; None for table metrics
    example: str


METRICS: tuple[Metric, ...] = (
    Metric(
        id="merchandise_revenue",
        name="Merchandise revenue",
        definition=(
            "Total item price of valid orders placed in the date range. Freight is excluded."
        ),
        synonyms=("sales", "revenue", "GMV", "merchandise value", "turnover"),
        args=DATES | {"state", "category"},
        notes=(ITEM_PRICES_ONLY, VALID_ORDERS, DATED_BY_PURCHASE),
        unit="brl",
        value_column="revenue",
        example="What were total sales in 2018?",
    ),
    Metric(
        id="order_count",
        name="Number of orders",
        definition="Number of valid orders placed in the date range.",
        synonyms=("orders", "number of orders", "order volume", "how many orders"),
        args=DATES | {"state"},
        notes=(VALID_ORDERS, "Counts orders, not items"),
        unit="count",
        value_column="orders",
        example="How many orders were placed in RJ in 2017?",
    ),
    Metric(
        id="average_order_value",
        name="Average order value",
        definition=(
            "Merchandise revenue divided by the number of valid orders that have at least one item."
        ),
        synonyms=("AOV", "average basket", "average order size", "average spend per order"),
        args=DATES | {"state"},
        notes=("Revenue ÷ orders, not the average item price", ITEM_PRICES_ONLY, VALID_ORDERS),
        unit="brl",
        value_column="average_order_value",
        example="What is the average order value?",
    ),
    Metric(
        id="monthly_revenue",
        name="Revenue by month",
        definition=(
            "Merchandise revenue and order count for each calendar month in the date range."
        ),
        synonyms=("revenue trend", "sales over time", "monthly sales", "revenue by month"),
        args=DATES | {"state", "category"},
        notes=(ITEM_PRICES_ONLY, VALID_ORDERS, DATED_BY_PURCHASE),
        unit="table",
        value_column=None,
        example="How did monthly sales develop during 2017?",
    ),
    Metric(
        id="top_categories_by_revenue",
        name="Top categories by revenue",
        definition="Product categories ranked by merchandise revenue.",
        synonyms=("best-selling categories by value", "highest-revenue categories"),
        args=DATES | {"state", "top_n"},
        notes=("Ranked by item price total; freight excluded", VALID_ORDERS),
        unit="table",
        value_column=None,
        example="Which five categories brought in the most money?",
    ),
    Metric(
        id="top_categories_by_units",
        name="Top categories by units sold",
        definition="Product categories ranked by number of units sold.",
        synonyms=(
            "most-sold categories",
            "best-selling categories by volume",
            "most popular categories",
        ),
        args=DATES | {"state", "top_n"},
        notes=("Ranked by units (item rows), not revenue", VALID_ORDERS),
        unit="table",
        value_column=None,
        example="Which categories sell the most units?",
    ),
    Metric(
        id="revenue_by_state",
        name="Revenue by customer state",
        definition="Customer states ranked by merchandise revenue.",
        synonyms=("sales by state", "top states", "revenue by region"),
        args=DATES | {"top_n"},
        notes=("State is the customer's state, not the seller's", ITEM_PRICES_ONLY, VALID_ORDERS),
        unit="table",
        value_column=None,
        example="Which states buy the most?",
    ),
    Metric(
        id="repeat_customer_rate",
        name="Repeat customer rate",
        definition=(
            "Of the customers who placed at least one valid order in the date range, the "
            "percentage who placed two or more."
        ),
        synonyms=(
            "repeat purchase rate",
            "returning customers",
            "customer retention",
            "loyalty",
        ),
        args=DATES,
        notes=(
            "A customer is a customer_unique_id",
            "Only orders inside the date range are counted",
            VALID_ORDERS,
        ),
        unit="percent",
        value_column="repeat_rate_pct",
        example="What share of customers came back for a second order?",
    ),
    Metric(
        id="late_delivery_rate",
        name="Late delivery rate",
        definition=(
            "Of delivered orders placed in the date range, the percentage delivered on a "
            "later calendar day than the estimated delivery date."
        ),
        synonyms=(
            "late orders",
            "delayed deliveries",
            "on-time delivery (the complement)",
            "delivery performance",
        ),
        args=DATES | {"state"},
        notes=(
            "Delivered orders with a delivery date only",
            "Late means delivered on a later calendar day than promised",
            DATED_BY_PURCHASE,
        ),
        unit="percent",
        value_column="late_rate_pct",
        example="How often did deliveries arrive late in 2018?",
    ),
    Metric(
        id="average_review_score",
        name="Average review score",
        definition=(
            "Average review score (1–5) of reviews on orders placed in the date range. With "
            "a category, only orders containing at least one item of that category."
        ),
        synonyms=("customer rating", "satisfaction score", "average rating", "review average"),
        args=DATES | {"category"},
        notes=(
            "Every review counts once",
            "All order statuses included",
            "Dated by the order's purchase time, not the review date",
        ),
        unit="score",
        value_column="average_score",
        example="How do customers rate health_beauty orders?",
    ),
)
