"""Create the OrderLens tables, load the Olist CSVs and create the read-only role.

Runs as the database owner (OWNER_DATABASE_URL). Safe to run twice: tables are dropped
and recreated, and the role is created or updated. Everything happens in one
transaction, so a failure leaves the database as it was.

Usage: uv run --env-file .env python scripts/setup_db.py
"""

import csv
from collections.abc import Iterator
from pathlib import Path

import psycopg
from psycopg import sql

from orderlens.config import settings

BACKEND_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BACKEND_DIR / "data" / "raw"
READONLY_ROLE = "orderlens_readonly"
TABLES_IN_LOAD_ORDER = [
    "customers",
    "sellers",
    "products",
    "orders",
    "order_items",
    "order_payments",
    "order_reviews",
]

# For every table except products, the table columns are named exactly like CSV columns,
# so loading means picking those columns and leaving the rest of the file behind.
CSV_SOURCES = {
    "customers": (
        "olist_customers_dataset.csv",
        ["customer_id", "customer_unique_id", "customer_city", "customer_state"],
    ),
    "sellers": ("olist_sellers_dataset.csv", ["seller_id", "seller_city", "seller_state"]),
    "orders": (
        "olist_orders_dataset.csv",
        [
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    ),
    "order_items": (
        "olist_order_items_dataset.csv",
        ["order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"],
    ),
    "order_payments": (
        "olist_order_payments_dataset.csv",
        [
            "order_id",
            "payment_sequential",
            "payment_type",
            "payment_installments",
            "payment_value",
        ],
    ),
    "order_reviews": (
        "olist_order_reviews_dataset.csv",
        ["review_id", "order_id", "review_score", "review_creation_date"],
    ),
}
PRODUCT_COLUMNS = ["product_id", "category", "product_weight_g"]


def read_csv(file_name: str) -> Iterator[dict[str, str | None]]:
    """Yield each CSV row as a dict, with empty strings turned into None."""
    # utf-8-sig strips the byte-order mark at the start of the translation file.
    with open(RAW_DIR / file_name, encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            yield {key: (value if value != "" else None) for key, value in row.items()}


def table_rows(table: str) -> Iterator[list[str | None]]:
    """Yield the rows to load into one of the tables that maps directly onto a CSV."""
    file_name, columns = CSV_SOURCES[table]
    for row in read_csv(file_name):
        yield [row[column] for column in columns]


def product_rows() -> list[list[str | None]]:
    """Build product rows with the category resolved to English, Portuguese or 'unknown'."""
    english_names = {
        row["product_category_name"]: row["product_category_name_english"]
        for row in read_csv("product_category_name_translation.csv")
    }
    rows = []
    untranslated = set()
    for row in read_csv("olist_products_dataset.csv"):
        portuguese = row["product_category_name"]
        if portuguese is not None and portuguese not in english_names:
            untranslated.add(portuguese)
        category = english_names.get(portuguese) or portuguese or "unknown"
        rows.append([row["product_id"], category, row["product_weight_g"]])
    print(f"categories with no English translation (kept in Portuguese): {sorted(untranslated)}")
    return rows


def copy_rows(
    cursor: psycopg.Cursor, table: str, columns: list[str], rows: Iterator | list
) -> None:
    """Stream rows into a table with COPY, which is much faster than row-by-row INSERTs."""
    statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, columns))
    )
    with cursor.copy(statement) as copy:
        for row in rows:
            copy.write_row(row)


def recreate_tables(conn: psycopg.Connection) -> None:
    """Drop the seven tables if they exist, then create them from sql/schema.sql."""
    for table in reversed(TABLES_IN_LOAD_ORDER):
        conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table)))
    conn.execute((BACKEND_DIR / "sql" / "schema.sql").read_text())


def load_tables(conn: psycopg.Connection) -> None:
    """Load every table from its CSV, parents before children so foreign keys hold."""
    with conn.cursor() as cursor:
        for table in TABLES_IN_LOAD_ORDER:
            print(f"loading {table}")
            if table == "products":
                copy_rows(cursor, table, PRODUCT_COLUMNS, product_rows())
            else:
                copy_rows(cursor, table, CSV_SOURCES[table][1], table_rows(table))


def create_readonly_role(conn: psycopg.Connection, password: str) -> None:
    """Create or update the read-only role: SELECT on the seven tables, 5-second timeout."""
    role_exists = conn.execute(
        "SELECT 1 FROM pg_roles WHERE rolname = %s", (READONLY_ROLE,)
    ).fetchone()
    # DDL cannot take bound parameters, so the password is quoted by psycopg's sql.Literal.
    action = "ALTER" if role_exists else "CREATE"
    conn.execute(
        sql.SQL("{} ROLE {} LOGIN PASSWORD {}").format(
            sql.SQL(action), sql.Identifier(READONLY_ROLE), sql.Literal(password)
        )
    )
    role = sql.Identifier(READONLY_ROLE)
    tables = sql.SQL(", ").join(map(sql.Identifier, TABLES_IN_LOAD_ORDER))
    conn.execute(sql.SQL("ALTER ROLE {} SET statement_timeout = '5s'").format(role))
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
    conn.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(tables, role))


# Each fact is compared by hand with ARCHITECTURE.md section 4.2.
FACT_QUERIES = {
    "orders": "SELECT COUNT(*) FROM orders",
    "order_items rows": "SELECT COUNT(*) FROM order_items",
    "orders with item rows": "SELECT COUNT(DISTINCT order_id) FROM order_items",
    "orders with no item rows": (
        "SELECT COUNT(*) FROM orders o"
        " WHERE NOT EXISTS (SELECT 1 FROM order_items oi WHERE oi.order_id = o.order_id)"
    ),
    "order_payments rows": "SELECT COUNT(*) FROM order_payments",
    "orders with more than one payment": (
        "SELECT COUNT(*) FROM (SELECT order_id FROM order_payments"
        " GROUP BY order_id HAVING COUNT(*) > 1) AS multi"
    ),
    "order_reviews rows": "SELECT COUNT(*) FROM order_reviews",
    "distinct review_id": "SELECT COUNT(DISTINCT review_id) FROM order_reviews",
    "customers (customer_id)": "SELECT COUNT(*) FROM customers",
    "customers (customer_unique_id)": "SELECT COUNT(DISTINCT customer_unique_id) FROM customers",
    "products": "SELECT COUNT(*) FROM products",
    "products with category 'unknown'": (
        "SELECT COUNT(*) FROM products WHERE category = 'unknown'"
    ),
    "distinct categories": "SELECT COUNT(DISTINCT category) FROM products",
    "sellers": "SELECT COUNT(*) FROM sellers",
    "customer states": "SELECT COUNT(DISTINCT customer_state) FROM customers",
    "delivered orders with no delivery date": (
        "SELECT COUNT(*) FROM orders"
        " WHERE order_status = 'delivered' AND order_delivered_customer_date IS NULL"
    ),
}


def print_facts(conn: psycopg.Connection) -> None:
    """Print the row counts, status breakdown and date window to check against the docs."""
    for label, query in FACT_QUERIES.items():
        print(f"{label:>40}: {conn.execute(query).fetchone()[0]:,}")
    first, last = conn.execute(
        "SELECT MIN(order_purchase_timestamp)::date, MAX(order_purchase_timestamp)::date"
        " FROM orders"
    ).fetchone()
    print(f"{'purchase dates':>40}: {first} to {last}")
    statuses = conn.execute(
        "SELECT order_status, COUNT(*) FROM orders GROUP BY order_status ORDER BY 2 DESC"
    ).fetchall()
    print(f"{'order statuses':>40}: " + " · ".join(f"{s} {n:,}" for s, n in statuses))


def main() -> None:
    """Run every setup step in one transaction, then print the facts."""
    if not settings.owner_database_url or not settings.readonly_password:
        raise SystemExit("OWNER_DATABASE_URL and READONLY_PASSWORD must be set in .env")
    with psycopg.connect(settings.owner_database_url) as conn:
        recreate_tables(conn)
        load_tables(conn)
        print("creating indexes")
        conn.execute((BACKEND_DIR / "sql" / "indexes.sql").read_text())
        print(f"creating or updating role {READONLY_ROLE}")
        create_readonly_role(conn, settings.readonly_password)
        print_facts(conn)
    print("committed")


if __name__ == "__main__":
    main()
