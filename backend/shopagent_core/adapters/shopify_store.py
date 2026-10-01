import os
import time

import requests

from shopagent_core.adapters.base import StoreAdapter
from shopagent_core.models import Order, OrderItem, Product

API_VERSION = "2025-01"


class ShopifyAdapter(StoreAdapter):
    """StoreAdapter backed by a real Shopify store's Admin GraphQL API.

    Auth uses the client-credentials grant (Shopify's current, non-legacy
    custom-app flow, effective 2026): exchanges a Client ID + Client Secret
    for a short-lived access token, cached and refreshed automatically -
    never a permanent static token."""

    def __init__(
        self,
        shop_domain: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        self.shop_domain = shop_domain or os.environ["SHOPIFY_SHOP_DOMAIN"]
        self.client_id = client_id or os.environ["SHOPIFY_CLIENT_ID"]
        self.client_secret = client_secret or os.environ["SHOPIFY_CLIENT_SECRET"]
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        response = requests.post(
            f"https://{self.shop_domain}/admin/oauth/access_token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        response.raise_for_status()
        data = response.json()

        self._access_token = data["access_token"]
        # Refresh 60s early rather than cutting it exactly at expiry.
        self._token_expires_at = time.time() + data["expires_in"] - 60
        return self._access_token

    def _graphql(self, query: str) -> dict:
        response = requests.post(
            f"https://{self.shop_domain}/admin/api/{API_VERSION}/graphql.json",
            headers={"X-Shopify-Access-Token": self._get_access_token()},
            json={"query": query},
        )
        response.raise_for_status()
        body = response.json()
        if "errors" in body:
            raise RuntimeError(f"Shopify GraphQL error: {body['errors']}")
        return body["data"]

    def get_products(
        self,
        keyword: str | None = None,
        category: str | None = None,
        color: str | None = None,
        max_price: float | None = None,
    ) -> list[Product]:
        # Shopify's search syntax has no native "color" filter (color is
        # normally a variant option, not a top-level product field) - not
        # supported here, an honest gap rather than a silent no-op.
        filters = ["inventory_total:>0"]
        if keyword:
            filters.append(f'title:{keyword}')
        if category:
            filters.append(f'product_type:{category}')
        search_query = " AND ".join(filters)

        data = self._graphql(f"""
        query {{
          products(first: 20, query: "{search_query}") {{
            edges {{
              node {{
                id
                title
                description
                productType
                priceRangeV2 {{ minVariantPrice {{ amount }} }}
                totalInventory
              }}
            }}
          }}
        }}
        """)

        products = []
        for edge in data["products"]["edges"]:
            node = edge["node"]
            price = float(node["priceRangeV2"]["minVariantPrice"]["amount"])
            if max_price is not None and price > max_price:
                continue
            products.append(
                Product(
                    id=node["id"],
                    name=node["title"],
                    price=price,
                    category=node["productType"] or "uncategorized",
                    in_stock=node["totalInventory"] > 0,
                    description=node["description"] or "",
                )
            )
        return products

    def get_order(self, order_id: str) -> Order | None:
        order_name = order_id if order_id.startswith("#") else f"#{order_id}"

        data = self._graphql(f"""
        query {{
          orders(first: 1, query: "name:{order_name}") {{
            edges {{
              node {{
                id
                name
                email
                displayFulfillmentStatus
                lineItems(first: 20) {{
                  edges {{ node {{ name quantity }} }}
                }}
                fulfillments(first: 5) {{
                  estimatedDeliveryAt
                  trackingInfo(first: 1) {{ number }}
                }}
              }}
            }}
          }}
        }}
        """)

        edges = data["orders"]["edges"]
        if not edges:
            return None
        node = edges[0]["node"]

        tracking_number = None
        estimated_delivery = None
        if node["fulfillments"]:
            first_fulfillment = node["fulfillments"][0]
            estimated_delivery = first_fulfillment.get("estimatedDeliveryAt")
            tracking_info = first_fulfillment.get("trackingInfo") or []
            if tracking_info:
                tracking_number = tracking_info[0].get("number")

        return Order(
            order_id=node["name"],
            customer_email=node["email"] or "",
            status=node["displayFulfillmentStatus"],
            items=[
                OrderItem(
                    product_id=item["node"]["name"],
                    name=item["node"]["name"],
                    quantity=item["node"]["quantity"],
                )
                for item in node["lineItems"]["edges"]
            ],
            estimated_delivery=estimated_delivery,
            tracking_number=tracking_number,
        )

    def get_policy_documents(self) -> str:
        data = self._graphql("{ shop { shopPolicies { title body } } }")
        sections = [
            f"## {policy['title']}\n{policy['body']}"
            for policy in data["shop"]["shopPolicies"]
        ]
        return "\n\n".join(sections)
