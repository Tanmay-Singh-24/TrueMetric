"""Compute the METRICS.md reference values from the raw CSVs, in plain Python.

No SQL and no database: this is a second, independent implementation of the metric
definitions, used to check the metric SQL. Each function below is named after the metric
it computes and returns the same columns as that metric. Writes
tests/reference_values.json.

Usage: uv run python scripts/reference_values.py
"""

import csv
import json
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BACKEND_DIR / "data" / "raw"
OUTPUT_PATH = BACKEND_DIR / "tests" / "reference_values.json"
INVALID_STATUSES = {"canceled", "unavailable"}
RANGES = {
    "all data": (date(2016, 9, 4), date(2018, 10, 17)),
    "2017": (date(2017, 1, 1), date(2017, 12, 31)),
    "2018": (date(2018, 1, 1), date(2018, 12, 31)),
}
TOP_N = 5

Result = tuple[list[str], list[list]]  # (column names, rows), the shape a query returns


@dataclass(frozen=True)
class Order:
    order_id: str
    status: str
    purchase_date: date
    customer_unique_id: str
    customer_state: str
    delivered_date: date | None
    estimated_date: date


@dataclass(frozen=True)
class Item:
    order_id: str
    category: str
    price: Decimal


@dataclass(frozen=True)
class Data:
    orders: dict[str, Order]
    items: list[Item]
    review_scores: list[tuple[str, int]]  # (order_id, review_score), one per review row


def read_csv(file_name: str) -> list[dict[str, str]]:
    """Read one raw CSV file into a list of dicts."""
    # utf-8-sig strips the byte-order mark at the start of the translation file.
    with open(RAW_DIR / file_name, encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def day(timestamp: str) -> date | None:
    """The calendar day of a 'YYYY-MM-DD hh:mm:ss' timestamp, or None if it is empty."""
    return date.fromisoformat(timestamp[:10]) if timestamp else None


def load_orders() -> dict[str, Order]:
    """Read orders, with each order's customer (person and state) attached."""
    customers = {row["customer_id"]: row for row in read_csv("olist_customers_dataset.csv")}
    orders = {}
    for row in read_csv("olist_orders_dataset.csv"):
        customer = customers[row["customer_id"]]
        orders[row["order_id"]] = Order(
            order_id=row["order_id"],
            status=row["order_status"],
            purchase_date=day(row["order_purchase_timestamp"]),
            customer_unique_id=customer["customer_unique_id"],
            customer_state=customer["customer_state"],
            delivered_date=day(row["order_delivered_customer_date"]),
            estimated_date=day(row["order_estimated_delivery_date"]),
        )
    return orders


def load_items() -> list[Item]:
    """Read order items, each with its product's category (English, else Portuguese)."""
    english = {
        row["product_category_name"]: row["product_category_name_english"]
        for row in read_csv("product_category_name_translation.csv")
    }
    category_of_product = {}
    for row in read_csv("olist_products_dataset.csv"):
        portuguese = row["product_category_name"]
        category_of_product[row["product_id"]] = english.get(portuguese) or portuguese or "unknown"
    return [
        Item(row["order_id"], category_of_product[row["product_id"]], Decimal(row["price"]))
        for row in read_csv("olist_order_items_dataset.csv")
    ]


def load_data() -> Data:
    """Read everything the metrics need from the raw CSVs."""
    reviews = [
        (row["order_id"], int(row["review_score"]))
        for row in read_csv("olist_order_reviews_dataset.csv")
    ]
    return Data(orders=load_orders(), items=load_items(), review_scores=reviews)


def round_2(value: Decimal) -> Decimal:
    """Round to two decimals, halves away from zero, as Postgres ROUND does."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def percentage(part: int, whole: int) -> Decimal | None:
    """part / whole as a percentage with two decimals, or None when whole is zero."""
    return round_2(Decimal(100) * part / whole) if whole else None


def counted_orders(data: Data, start_date: date, end_date: date, state: str | None) -> list[Order]:
    """Valid orders placed between the two dates (inclusive), optionally in one state."""
    return [
        order
        for order in data.orders.values()
        if order.status not in INVALID_STATUSES
        and start_date <= order.purchase_date <= end_date
        and (state is None or order.customer_state == state)
    ]


def counted_items(
    data: Data, start_date: date, end_date: date, state: str | None, category: str | None
) -> list[Item]:
    """Items of the counted orders, optionally only those of one category."""
    order_ids = {order.order_id for order in counted_orders(data, start_date, end_date, state)}
    return [
        item
        for item in data.items
        if item.order_id in order_ids and (category is None or item.category == category)
    ]


def merchandise_revenue(
    data: Data, start_date: date, end_date: date, state: str | None, category: str | None
) -> Result:
    """Total item price of valid orders in the range, and how many orders that covers."""
    items = counted_items(data, start_date, end_date, state, category)
    revenue = sum((item.price for item in items), Decimal(0))
    return ["revenue", "orders"], [[revenue, len({item.order_id for item in items})]]


def order_count(data: Data, start_date: date, end_date: date, state: str | None) -> Result:
    """Number of valid orders placed in the range."""
    return ["orders"], [[len(counted_orders(data, start_date, end_date, state))]]


def average_order_value(data: Data, start_date: date, end_date: date, state: str | None) -> Result:
    """Revenue divided by the number of valid orders that have at least one item."""
    items = counted_items(data, start_date, end_date, state, None)
    orders = len({item.order_id for item in items})
    revenue = sum((item.price for item in items), Decimal(0))
    value = round_2(revenue / orders) if orders else None
    return ["average_order_value", "orders"], [[value, orders]]


def monthly_revenue(
    data: Data, start_date: date, end_date: date, state: str | None, category: str | None
) -> Result:
    """Revenue and order count per calendar month of purchase."""
    revenue_by_month = defaultdict(Decimal)
    orders_by_month = defaultdict(set)
    for item in counted_items(data, start_date, end_date, state, category):
        purchased = data.orders[item.order_id].purchase_date
        month = date(purchased.year, purchased.month, 1)
        revenue_by_month[month] += item.price
        orders_by_month[month].add(item.order_id)
    rows = [
        [month, revenue_by_month[month], len(orders_by_month[month])]
        for month in sorted(revenue_by_month)
    ]
    return ["month", "revenue", "orders"], rows


def category_totals(data: Data, start_date: date, end_date: date, state: str | None) -> list[list]:
    """[category, revenue, units] for every category with counted items."""
    revenue = defaultdict(Decimal)
    units = Counter()
    for item in counted_items(data, start_date, end_date, state, None):
        revenue[item.category] += item.price
        units[item.category] += 1
    return [[category, revenue[category], units[category]] for category in revenue]


def top_categories_by_revenue(
    data: Data, start_date: date, end_date: date, state: str | None, top_n: int
) -> Result:
    """Categories ranked by revenue (ties by name)."""
    rows = category_totals(data, start_date, end_date, state)
    rows.sort(key=lambda row: (-row[1], row[0]))
    return ["category", "revenue", "units"], rows[:top_n]


def top_categories_by_units(
    data: Data, start_date: date, end_date: date, state: str | None, top_n: int
) -> Result:
    """Categories ranked by units sold (ties by name)."""
    rows = category_totals(data, start_date, end_date, state)
    rows.sort(key=lambda row: (-row[2], row[0]))
    return ["category", "revenue", "units"], rows[:top_n]


def revenue_by_state(data: Data, start_date: date, end_date: date, top_n: int) -> Result:
    """Customer states ranked by revenue (ties by state code)."""
    revenue = defaultdict(Decimal)
    orders = defaultdict(set)
    for item in counted_items(data, start_date, end_date, None, None):
        state = data.orders[item.order_id].customer_state
        revenue[state] += item.price
        orders[state].add(item.order_id)
    rows = [[state, revenue[state], len(orders[state])] for state in revenue]
    rows.sort(key=lambda row: (-row[1], row[0]))
    return ["state", "revenue", "orders"], rows[:top_n]


def repeat_customer_rate(data: Data, start_date: date, end_date: date) -> Result:
    """Share of people (customer_unique_id) with two or more valid orders in the range."""
    orders_per_person = Counter(
        order.customer_unique_id for order in counted_orders(data, start_date, end_date, None)
    )
    repeat = sum(1 for count in orders_per_person.values() if count >= 2)
    customers = len(orders_per_person)
    columns = ["repeat_rate_pct", "repeat_customers", "customers"]
    return columns, [[percentage(repeat, customers), repeat, customers]]


def late_delivery_rate(data: Data, start_date: date, end_date: date, state: str | None) -> Result:
    """Share of delivered orders that arrived on a later day than promised."""
    delivered = [
        order
        for order in data.orders.values()
        if order.status == "delivered"
        and order.delivered_date is not None
        and start_date <= order.purchase_date <= end_date
        and (state is None or order.customer_state == state)
    ]
    late = sum(1 for order in delivered if order.delivered_date > order.estimated_date)
    columns = ["late_rate_pct", "late_orders", "delivered_orders"]
    return columns, [[percentage(late, len(delivered)), late, len(delivered)]]


def average_review_score(
    data: Data, start_date: date, end_date: date, category: str | None
) -> Result:
    """Average score of reviews on orders placed in the range, any order status."""
    orders_with_category = {item.order_id for item in data.items if item.category == category}
    scores = [
        score
        for order_id, score in data.review_scores
        if start_date <= data.orders[order_id].purchase_date <= end_date
        and (category is None or order_id in orders_with_category)
    ]
    average = round_2(Decimal(sum(scores)) / len(scores)) if scores else None
    return ["average_score", "reviews"], [[average, len(scores)]]


def make_case(label: str, metric_function: Callable[..., Result], data: Data, args: dict) -> dict:
    """Run one metric function and package its result with the arguments that produced it."""
    columns, rows = metric_function(data, **args)
    return {
        "label": f"{metric_function.__name__} / {label}",
        "metric_id": metric_function.__name__,
        "args": args,
        "columns": columns,
        "rows": rows,
    }


def date_args(label: str) -> dict[str, date]:
    """The start_date and end_date arguments for one of the named ranges."""
    start_date, end_date = RANGES[label]
    return {"start_date": start_date, "end_date": end_date}


def cases_for_range(data: Data, label: str) -> list[dict]:
    """Every metric, unfiltered, over one named date range."""
    dates = date_args(label)
    return [
        make_case(label, merchandise_revenue, data, {**dates, "state": None, "category": None}),
        make_case(label, order_count, data, {**dates, "state": None}),
        make_case(label, average_order_value, data, {**dates, "state": None}),
        make_case(label, monthly_revenue, data, {**dates, "state": None, "category": None}),
        make_case(label, top_categories_by_revenue, data, {**dates, "state": None, "top_n": TOP_N}),
        make_case(label, top_categories_by_units, data, {**dates, "state": None, "top_n": TOP_N}),
        make_case(label, revenue_by_state, data, {**dates, "top_n": TOP_N}),
        make_case(label, repeat_customer_rate, data, dates),
        make_case(label, late_delivery_rate, data, {**dates, "state": None}),
        make_case(label, average_review_score, data, {**dates, "category": None}),
    ]


def spot_check_cases(data: Data) -> list[dict]:
    """The three filtered spot checks from METRICS.md."""
    return [
        make_case(
            "2018, state SP",
            merchandise_revenue,
            data,
            {**date_args("2018"), "state": "SP", "category": None},
        ),
        make_case(
            "2017, health_beauty",
            merchandise_revenue,
            data,
            {**date_args("2017"), "state": None, "category": "health_beauty"},
        ),
        make_case(
            "all data, health_beauty",
            average_review_score,
            data,
            {**date_args("all data"), "category": "health_beauty"},
        ),
    ]


def to_json(value: object) -> str:
    """JSON has no Decimal or date: write both as exact strings."""
    if isinstance(value, Decimal | date):
        return str(value)
    raise TypeError(f"cannot write {type(value).__name__} to JSON")


def row_multiplication_trap(data: Data) -> dict[str, Decimal]:
    """Payment totals for valid orders, with and without the items join, plus freight."""
    valid = {
        order.order_id for order in data.orders.values() if order.status not in INVALID_STATUSES
    }
    item_rows = read_csv("olist_order_items_dataset.csv")
    item_rows_per_order = Counter(row["order_id"] for row in item_rows)
    payments = [
        (row["order_id"], Decimal(row["payment_value"]))
        for row in read_csv("olist_order_payments_dataset.csv")
        if row["order_id"] in valid
    ]
    # Joining items repeats each payment once per item row; orders with no items drop out.
    return {
        "true_payment_total": sum(value for _, value in payments),
        "payment_total_after_joining_items": sum(
            value * item_rows_per_order[order_id] for order_id, value in payments
        ),
        "total_freight": sum(
            Decimal(row["freight_value"]) for row in item_rows if row["order_id"] in valid
        ),
    }


def main() -> None:
    """Compute every case, print it, and write tests/reference_values.json."""
    data = load_data()
    cases = []
    for label in RANGES:
        cases += cases_for_range(data, label)
    cases += spot_check_cases(data)
    for case in cases:
        print(f"{case['label']}  {case['columns']}")
        for row in case["rows"]:
            print("    " + "  ".join(str(value) for value in row))
    trap = row_multiplication_trap(data)
    for name, value in trap.items():
        print(f"{name}: {value}")
    output = {"metric_cases": cases, "row_multiplication_trap": trap}
    OUTPUT_PATH.write_text(json.dumps(output, indent=1, default=to_json) + "\n")
    print(f"wrote {len(cases)} metric cases to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
