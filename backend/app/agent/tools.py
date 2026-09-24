import json
from typing import Literal

from langchain_core.tools import tool

from app.services.order_lookup import get_order_status as _get_order_status
from app.services.policy_rag import retrieve_policy as _retrieve_policy
from app.services.product_search import search_products as _search_products

MOCK_STORE_ID = "store_mock_001"

ProductCategory = Literal["shoes", "electronics", "home", "fitness"]


@tool
def search_products(
    keyword: str | None = None,
    category: ProductCategory | None = None,
    color: str | None = None,
    max_price: float | None = None,
) -> str:
    """Search the store's product catalog. Use this when the customer asks about
    finding, browsing, or getting recommendations for products (e.g. "do you have
    running shoes under $80?"). `category` must be one of: shoes, electronics,
    home, fitness. For more specific terms like "running" or "hiking", pass them
    via `keyword` instead of `category`. Any filter can be omitted."""
    results = _search_products(
        keyword=keyword, category=category, color=color, max_price=max_price
    )
    return json.dumps(results)


@tool
def get_order_status(order_id: str) -> str:
    """Look up a specific order's status by its order ID (e.g. "ORD1001"). Use this
    when the customer asks where their order is, its delivery status, tracking
    number, or whether it can still be cancelled."""
    return json.dumps(_get_order_status(order_id))


@tool
def search_policies(query: str) -> str:
    """Search the store's shipping, return, refund, warranty, and cancellation
    policies. Use this when the customer asks a policy question (e.g. "can I
    return this?", "do you ship internationally?")."""
    return json.dumps(_retrieve_policy(query, store_id=MOCK_STORE_ID))


TOOLS = [search_products, get_order_status, search_policies]
