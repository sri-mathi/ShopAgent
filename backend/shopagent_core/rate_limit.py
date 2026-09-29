import time

# In-memory only: lost on server restart, not shared across multiple server
# processes - same honest MVP limitation as session memory and the in-memory
# Chroma collections. A real deployment needs this in Redis instead, since
# rate limits must hold across all processes/replicas to mean anything.
_request_log: dict[str, list[float]] = {}

MAX_REQUESTS = 20
WINDOW_SECONDS = 60


def check_rate_limit(
    key: str,
    max_requests: int = MAX_REQUESTS,
    window_seconds: int = WINDOW_SECONDS,
) -> bool:
    now = time.time()
    window_start = now - window_seconds
    timestamps = _request_log.setdefault(key, [])

    while timestamps and timestamps[0] < window_start:
        timestamps.pop(0)

    if len(timestamps) >= max_requests:
        return False

    timestamps.append(now)
    return True
