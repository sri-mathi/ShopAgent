import uuid

from app.rate_limit import check_rate_limit


def test_allows_requests_under_the_limit():
    key = f"rate-limit-test-{uuid.uuid4()}"
    for _ in range(3):
        assert check_rate_limit(key, max_requests=3, window_seconds=60)


def test_blocks_requests_over_the_limit():
    key = f"rate-limit-test-{uuid.uuid4()}"
    for _ in range(3):
        check_rate_limit(key, max_requests=3, window_seconds=60)
    assert not check_rate_limit(key, max_requests=3, window_seconds=60)


def test_different_keys_have_independent_limits():
    key_a = f"rate-limit-test-a-{uuid.uuid4()}"
    key_b = f"rate-limit-test-b-{uuid.uuid4()}"
    for _ in range(3):
        check_rate_limit(key_a, max_requests=3, window_seconds=60)

    assert not check_rate_limit(key_a, max_requests=3, window_seconds=60)
    assert check_rate_limit(key_b, max_requests=3, window_seconds=60)
