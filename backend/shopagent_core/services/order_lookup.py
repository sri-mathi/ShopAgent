import json
from pathlib import Path

from shopagent_core.adapters.base import StoreAdapter

DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "orders.json"

GENERIC_VERIFICATION_ERROR = {
    "error": "We couldn't verify an order with that ID and email. Please double-check both and try again."
}


def load_orders(orders_path: str | Path | None = None) -> list[dict]:
    with open(orders_path or DEFAULT_DATA_PATH) as f:
        return json.load(f)


def find_order(order_id: str, orders_path: str | Path | None = None) -> dict | None:
    """Raw fetch by ID only - no ownership check. Used directly by
    JSONFileStoreAdapter, and indirectly by any adapter backed by these
    flat files."""
    orders = load_orders(orders_path)
    for order in orders:
        if order["order_id"] == order_id:
            return order
    return None


def get_order_status(adapter: StoreAdapter, order_id: str, email: str) -> dict:
    """The centralized ownership check every store's data goes through,
    regardless of which adapter is configured. A wrong email and a
    nonexistent order must be indistinguishable - both return the exact
    same generic error - otherwise an attacker could enumerate valid order
    IDs by noticing which failure message came back. This lives here, not
    on the adapter, so no adapter author can accidentally get it wrong."""
    order = adapter.get_order(order_id)
    if order is None or order.customer_email.lower() != email.strip().lower():
        return GENERIC_VERIFICATION_ERROR
    return order.model_dump()
