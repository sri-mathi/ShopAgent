import os
import sys
from pathlib import Path

# Evals test OUR agent logic against KNOWN mock data - they must never
# depend on whatever store a developer's own .env happens to be pointed at
# that day (e.g. STORE_ADAPTER_TYPE=shopify while testing a real
# integration). Force this before any shopagent_core module gets imported,
# since store_config.py reads it at import time to build its adapter
# singleton.
os.environ["STORE_ADAPTER_TYPE"] = "json"

BACKEND_PATH = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))
