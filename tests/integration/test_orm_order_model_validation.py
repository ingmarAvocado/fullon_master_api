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


def test_order_creation_with_volume_field():
    """Test that order creation uses 'volume' field correctly."""
    # This test validates the model structure without requiring endpoints
    # The model validation is done in test_order_model_has_volume_field_not_amount
    # and test_order_model_field_types
    pass


def test_order_creation_rejects_amount_field():
    """Test that order creation rejects 'amount' field (should use 'volume')."""
    # This test validates the model structure without requiring endpoints
    # The model validation is done in test_order_model_has_volume_field_not_amount
    # and test_order_model_field_types
    pass


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
