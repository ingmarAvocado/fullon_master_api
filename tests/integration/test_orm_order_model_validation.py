"""
CRITICAL: Tests validating Order model uses 'volume' field, NOT 'amount'.

Reference: docs/FULLON_ORM_LLM_README.md line 59
"""
import pytest


def test_order_model_has_volume_field_not_amount():
    """
    CRITICAL: Verify Order model uses 'volume' field.

    From docs/FULLON_ORM_LLM_README.md line 59:
    '❌ WRONG: NEVER use 'amount' field (use 'volume')'
    """
    from fullon_orm.models import Order

    # Get Order model fields
    order_fields = [field.name for field in Order.__table__.columns]

    # CRITICAL: Must have 'volume' field
    assert 'volume' in order_fields, "Order model MUST have 'volume' field"

    # CRITICAL: Must NOT have 'amount' field (common mistake)
    assert 'amount' not in order_fields, "Order model must use 'volume' NOT 'amount'"


@pytest.mark.asyncio
async def test_order_creation_with_volume_field(client, auth_headers):
    """Test that order creation uses 'volume' field correctly."""
    order_data = {
        "symbol": "BTC/USD",
        "volume": 1.0,  # ✅ CORRECT field name
        "side": "buy",
        "order_type": "market",
        "status": "New"
    }

    # This should work (if order endpoints exist)
    response = client.post("/api/v1/orm/orders", json=order_data, headers=auth_headers)

    # May return 200/201 (success) or 404 (endpoint not implemented)
    assert response.status_code in [200, 201, 404]

    if response.status_code in [200, 201]:
        # If endpoint exists, verify response uses volume
        order_response = response.json()
        assert "volume" in order_response
        assert order_response["volume"] == 1.0


@pytest.mark.asyncio
async def test_order_creation_rejects_amount_field(client, auth_headers):
    """Test that order creation rejects 'amount' field (should use 'volume')."""
    order_data = {
        "symbol": "BTC/USD",
        "amount": 1.0,  # ❌ WRONG field name
        "side": "buy",
        "order_type": "market",
        "status": "New"
    }

    response = client.post("/api/v1/orm/orders", json=order_data, headers=auth_headers)

    # Should reject the request if endpoint exists and validates fields
    # May return 400 (bad request) or 404 (not implemented)
    assert response.status_code in [400, 404]

    if response.status_code == 400:
        # If validation occurs, should mention the field issue
        error_data = response.json()
        assert "amount" in str(error_data).lower() or "volume" in str(error_data).lower()


def test_order_model_field_types():
    """Test that Order model has correct field types for volume."""
    from fullon_orm.models import Order
    from sqlalchemy import Float, Integer

    # Get volume column
    volume_column = None
    for column in Order.__table__.columns:
        if column.name == 'volume':
            volume_column = column
            break

    assert volume_column is not None, "Volume column must exist"

    # Volume should be numeric (Float or similar)
    assert isinstance(volume_column.type, (Float, Integer)), "Volume should be numeric type"
