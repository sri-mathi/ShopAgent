import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "orders.json"


def load_orders() -> list[dict]:
    with open(DATA_PATH) as f:
        return json.load(f)


def get_order_status(order_id: str) -> dict:
    orders = load_orders()
    for order in orders:
        if order["order_id"] == order_id:
            return order
    return {"error": f"No order found with ID '{order_id}'"}
