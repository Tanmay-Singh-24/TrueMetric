from truemetric.schema import TABLE_COLUMNS, parse_tables


def test_schema_has_the_seven_tables() -> None:
    assert set(TABLE_COLUMNS) == {
        "customers",
        "sellers",
        "products",
        "orders",
        "order_items",
        "order_payments",
        "order_reviews",
    }


def test_columns_are_parsed_with_their_types() -> None:
    assert TABLE_COLUMNS["order_items"] == {
        "order_id": "text",
        "order_item_id": "int",
        "product_id": "text",
        "seller_id": "text",
        "price": "decimal(10, 2)",
        "freight_value": "decimal(10, 2)",
    }


def test_table_constraints_are_not_mistaken_for_columns() -> None:
    tables = parse_tables("CREATE TABLE t (a text, b integer, PRIMARY KEY (a, b));")
    assert tables == {"t": {"a": "text", "b": "int"}}
