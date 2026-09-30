from shopagent_core.adapters.base import StoreAdapter
from shopagent_core.adapters.json_file_store import JSONFileStoreAdapter

# A self-hosted ShopAgent-OS instance serves exactly one store, configured
# once at startup via environment variables (see JSONFileStoreAdapter and
# .env.example) - not a multi-tenant registry routed per-request. A real
# multi-tenant SaaS deployment (many stores, one running server) would
# replace this with a lookup keyed by store_id instead; not needed yet.
_adapter: StoreAdapter = JSONFileStoreAdapter()


def get_store_adapter() -> StoreAdapter:
    return _adapter
