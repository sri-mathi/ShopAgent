import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "orders.json"


def load_orders() -> list[dict]:
    with open(DATA_PATH) as f:
        return json.load(f)


GENERIC_VERIFICATION_ERROR = {
    "error": "We couldn't verify an order with that ID and email. Please double-check both and try again."
}


def get_order_status(order_id: str, email: str) -> dict:
    orders = load_orders()
    for order in orders:
        if (
            order["order_id"] == order_id
            and order["customer_email"].lower() == email.strip().lower()
        ):
            return order
    return GENERIC_VERIFICATION_ERROR
