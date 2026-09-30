import os
from pathlib import Path

from shopagent_core.adapters.base import StoreAdapter
from shopagent_core.models import Order, Product
from shopagent_core.services.order_lookup import find_order
from shopagent_core.services.policy_rag import load_policy_text
from shopagent_core.services.product_search import search_products


class JSONFileStoreAdapter(StoreAdapter):
    """A generic StoreAdapter backed by three flat files - a products.json,
    an orders.json, and a policy text/markdown file. Any store owner without
    a Shopify/WooCommerce backend can use this directly by pointing it at
    their own files (via constructor args, or the SHOPAGENT_PRODUCTS_PATH /
    SHOPAGENT_ORDERS_PATH / SHOPAGENT_POLICIES_PATH env vars) - no custom
    adapter code required, as long as their files match the same schema as
    the bundled mock data."""

    def __init__(
        self,
        products_path: str | Path | None = None,
        orders_path: str | Path | None = None,
        policies_path: str | Path | None = None,
    ):
        self.products_path = products_path or os.environ.get("SHOPAGENT_PRODUCTS_PATH")
        self.orders_path = orders_path or os.environ.get("SHOPAGENT_ORDERS_PATH")
        self.policies_path = policies_path or os.environ.get("SHOPAGENT_POLICIES_PATH")

    def get_products(
        self,
        keyword: str | None = None,
        category: str | None = None,
        color: str | None = None,
        max_price: float | None = None,
    ) -> list[Product]:
        raw_results = search_products(
            keyword=keyword,
            category=category,
            color=color,
            max_price=max_price,
            products_path=self.products_path,
        )
        return [Product(**raw) for raw in raw_results]

    def get_order(self, order_id: str) -> Order | None:
        raw = find_order(order_id, orders_path=self.orders_path)
        return Order(**raw) if raw else None

    def get_policy_documents(self) -> str:
        return load_policy_text(self.policies_path)
