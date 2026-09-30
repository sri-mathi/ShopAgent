import json
from pathlib import Path

DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "products.json"


def load_products(products_path: str | Path | None = None) -> list[dict]:
    with open(products_path or DEFAULT_DATA_PATH) as f:
        return json.load(f)


def search_products(
    keyword: str | None = None,
    category: str | None = None,
    color: str | None = None,
    max_price: float | None = None,
    products_path: str | Path | None = None,
) -> list[dict]:
    products = load_products(products_path)
    results = []

    for product in products:
        if not product["in_stock"]:
            continue
        if category and product["category"] != category:
            continue
        if color and product["color"] != color:
            continue
        if max_price is not None and product["price"] > max_price:
            continue
        if keyword:
            haystack = " ".join(
                [product["name"], product["description"], *product["tags"]]
            ).lower()
            if keyword.lower() not in haystack:
                continue
        results.append(product)

    return results
