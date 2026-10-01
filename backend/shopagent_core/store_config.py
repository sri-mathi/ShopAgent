import os

from shopagent_core.adapters.base import StoreAdapter
from shopagent_core.adapters.json_file_store import JSONFileStoreAdapter

# A self-hosted ShopAgent-OS instance serves exactly one store, configured
# once at startup via environment variables - not a multi-tenant registry
# routed per-request. A real multi-tenant SaaS deployment (many stores, one
# running server) would replace this with a lookup keyed by store_id
# instead; not needed yet.
#
# STORE_ADAPTER_TYPE selects which backend this deployment talks to:
#   "json" (default) - flat files, see JSONFileStoreAdapter / .env.example
#   "shopify"         - a real Shopify store, see ShopifyAdapter / .env.example


def _build_adapter() -> StoreAdapter:
    adapter_type = os.environ.get("STORE_ADAPTER_TYPE", "json")

    if adapter_type == "shopify":
        from shopagent_core.adapters.shopify_store import ShopifyAdapter

        return ShopifyAdapter()

    if adapter_type == "json":
        return JSONFileStoreAdapter()

    raise ValueError(
        f"Unknown STORE_ADAPTER_TYPE: {adapter_type!r} (expected 'json' or 'shopify')"
    )


_adapter: StoreAdapter = _build_adapter()


def get_store_adapter() -> StoreAdapter:
    return _adapter
