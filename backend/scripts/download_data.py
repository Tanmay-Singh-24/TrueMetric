"""Download the eight Olist CSV files used by OrderLens into backend/data/raw/.

Source: https://github.com/olist/work-at-olist-data (MIT licence). The geolocation file
is not downloaded because nothing uses it.
"""

import urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets/"
FILES = [
    "olist_customers_dataset.csv",
    "olist_sellers_dataset.csv",
    "olist_products_dataset.csv",
    "product_category_name_translation.csv",
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
]
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def main() -> None:
    """Fetch each file, skipping any that is already on disk."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        target = RAW_DIR / name
        if target.exists():
            print(f"already have {name}")
            continue
        print(f"downloading {name}")
        urllib.request.urlretrieve(BASE_URL + name, target)
    print(f"done: {RAW_DIR}")


if __name__ == "__main__":
    main()
