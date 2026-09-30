from pydantic import BaseModel


class Product(BaseModel):
    id: str
    name: str
    price: float
    category: str
    color: str | None = None
    in_stock: bool = True
    description: str = ""


class OrderItem(BaseModel):
    product_id: str
    name: str
    quantity: int


class Order(BaseModel):
    order_id: str
    customer_email: str
    status: str
    items: list[OrderItem]
    estimated_delivery: str | None = None
    tracking_number: str | None = None
