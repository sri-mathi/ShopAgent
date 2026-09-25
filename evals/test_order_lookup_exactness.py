from app.services.order_lookup import get_order_status

EXACT_CASES = [
    ("ORD1001", {"status": "shipped", "tracking_number": "TRK-88213"}),
    ("ORD1004", {"status": "cancelled", "tracking_number": None}),
]


def test_order_lookup_returns_exact_fields():
    for order_id, expected_subset in EXACT_CASES:
        result = get_order_status(order_id)
        for key, expected_value in expected_subset.items():
            assert result[key] == expected_value, (
                f"{order_id}: expected {key}={expected_value!r}, got {result.get(key)!r}"
            )


def test_order_lookup_unknown_id_returns_error():
    result = get_order_status("ORD_DOES_NOT_EXIST")
    assert "error" in result
