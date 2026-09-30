# Connecting Your Own Store Data

ShopAgent-OS never requires you to fork or modify its agent logic to use your
own store's products, orders, or policies. There are two ways to connect your
data, depending on what you have.

## Option 1: You have flat files (most common - start here)

If your product catalog, order data, and policy text can be exported as
simple files, use the built-in `JSONFileStoreAdapter` - no code required.

Set these in your `.env` (all optional; omit any to fall back to the bundled
mock data):

```
SHOPAGENT_PRODUCTS_PATH=/path/to/your/products.json
SHOPAGENT_ORDERS_PATH=/path/to/your/orders.json
SHOPAGENT_POLICIES_PATH=/path/to/your/policies.md
```

Your files must match this schema:

**`products.json`** - a JSON array of objects:
```json
{
  "id": "string, unique",
  "name": "string",
  "category": "string",
  "price": 0.0,
  "color": "string or null",
  "tags": ["array", "of", "strings"],
  "in_stock": true,
  "description": "string"
}
```

**`orders.json`** - a JSON array of objects:
```json
{
  "order_id": "string, unique",
  "customer_email": "string",
  "status": "string, e.g. shipped/processing/delivered/cancelled",
  "items": [{"product_id": "string", "name": "string", "quantity": 1}],
  "estimated_delivery": "string or null",
  "tracking_number": "string or null"
}
```

**`policies.md`** - plain text or markdown, any length, with or without `##`
headings (both are handled - see how chunking works in `docs/LEARNING.md`).

That's it. Restart your backend and the agent answers from your data.

## Option 2: Your data lives somewhere else (a real database, Shopify, a CMS)

Implement `StoreAdapter` (`backend/shopagent_core/adapters/base.py`) - three
methods:

```python
class StoreAdapter(ABC):
    def get_products(self, keyword=None, category=None, color=None, max_price=None) -> list[Product]: ...
    def get_order(self, order_id: str) -> Order | None: ...
    def get_policy_documents(self) -> str: ...
```

`Product` and `Order` are defined in `shopagent_core/models.py` - return
objects of those exact shapes.

**The one rule that matters most: keep these methods dumb.** `get_order`
takes only an ID and returns the order if it exists - **do not** check the
customer's email inside your adapter. Ownership verification (and the
guarantee that a wrong email and a nonexistent order are indistinguishable,
so an attacker can't enumerate valid order IDs by comparing error messages)
is handled centrally in `services/order_lookup.py`, applied identically to
every adapter. Reimplementing that check yourself risks getting the
security-sensitive part wrong even if your data-fetching is perfect.

Similarly, `get_policy_documents` just returns raw text. Chunking, embedding,
and similarity search are handled centrally in `services/policy_rag.py` - you
don't need to build any retrieval logic, just hand back your policy text
however your system stores it.

Use `JSONFileStoreAdapter` (`adapters/json_file_store.py`) as your reference
implementation - copy its structure for your own backend.

Once written, point `shopagent_core/store_config.py`'s `get_store_adapter()`
at your adapter instead of `JSONFileStoreAdapter()`.
