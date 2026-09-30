import json
from typing import Literal

from langchain_core.tools import tool

from shopagent_core.services.order_lookup import get_order_status as _get_order_status
from shopagent_core.services.policy_rag import retrieve_policy as _retrieve_policy
from shopagent_core.store_config import get_store_adapter

STORE_ID = "default"

ProductCategory = Literal["shoes", "electronics", "home", "fitness"]

_adapter = get_store_adapter()


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
    results = _adapter.get_products(
        keyword=keyword, category=category, color=color, max_price=max_price
    )
    return json.dumps([product.model_dump() for product in results])


@tool
def get_order_status(order_id: str, email: str) -> str:
    """Look up a specific order's status. Requires BOTH the order ID (e.g.
    "ORD1001") AND the email address used to place that order, to verify the
    customer is the order's actual owner. If the customer has only given the
    order ID, ask them for the email on that order before calling this tool -
    do not guess or reuse an email from earlier in the conversation for a
    different order. Use this when the customer asks where their order is,
    its delivery status, tracking number, or whether it can still be
    cancelled."""
    return json.dumps(_get_order_status(_adapter, order_id, email))


@tool
def search_policies(query: str) -> str:
    """Search the store's shipping, return, refund, warranty, and cancellation
    policies. Use this when the customer asks a policy question (e.g. "can I
    return this?", "do you ship internationally?")."""
    return json.dumps(_retrieve_policy(query, store_id=STORE_ID, adapter=_adapter))


TOOLS = [search_products, get_order_status, search_policies]
