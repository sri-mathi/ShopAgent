from shopagent_core.adapters.json_file_store import JSONFileStoreAdapter
from shopagent_core.services.order_lookup import get_order_status

adapter = JSONFileStoreAdapter()

EXACT_CASES = [
    ("ORD1001", "alice@example.com", {"status": "shipped", "tracking_number": "TRK-88213"}),
    ("ORD1004", "carla@example.com", {"status": "cancelled", "tracking_number": None}),
]


def test_order_lookup_returns_exact_fields():
    for order_id, email, expected_subset in EXACT_CASES:
        result = get_order_status(adapter, order_id, email)
        for key, expected_value in expected_subset.items():
            assert result[key] == expected_value, (
                f"{order_id}: expected {key}={expected_value!r}, got {result.get(key)!r}"
            )


def test_order_lookup_unknown_id_returns_error():
    result = get_order_status(adapter, "ORD_DOES_NOT_EXIST", "someone@example.com")
    assert "error" in result


def test_order_lookup_rejects_wrong_email():
    result = get_order_status(adapter, "ORD1001", "not-the-real-owner@example.com")
    assert "error" in result


def test_no_enumeration_side_channel():
    """A wrong email on a real order must be indistinguishable from a
    nonexistent order - otherwise an attacker could enumerate valid order
    IDs just by seeing which error message comes back."""
    wrong_email_on_real_order = get_order_status(adapter, "ORD1001", "attacker@evil.com")
    nonexistent_order = get_order_status(adapter, "ORD9999", "attacker@evil.com")
    assert wrong_email_on_real_order == nonexistent_order
