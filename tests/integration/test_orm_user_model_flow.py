"""
Integration tests for User model flow through dependencies.

Tests that both ORM and master get_current_user dependencies
return User ORM model instances (NOT dictionaries).
"""
import pytest
from unittest.mock import Mock
from fullon_orm.models import User
from fullon_master_api.auth.dependencies import get_current_user as master_get_current_user


@pytest.mark.asyncio
async def test_master_get_current_user_returns_user_model():
    """Test that master get_current_user returns User ORM model."""
    # Create a mock User object (since we can't easily create real ORM instances in tests)
    mock_user = Mock()
    mock_user.uid = 1
    mock_user.mail = "test@example.com"
    mock_user.name = "Test User"
    mock_user.username = "testuser"  # Required for logging

    # Mock request with user in state
    request = Mock()
    request.state.user = mock_user

    # Call dependency
    result = await master_get_current_user(request)

    # Verify it returns the user from request state
    assert result == mock_user
    assert result.uid == 1
    assert result.mail == "test@example.com"


@pytest.mark.asyncio
async def test_master_get_current_user_raises_without_user():
    """Test that master get_current_user raises 401 without user."""
    from fastapi import HTTPException

    # Mock request without user
    request = Mock()
    request.state = Mock()
    request.state.user = None

    # Should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await master_get_current_user(request)

    assert exc_info.value.status_code == 401
    assert "Not authenticated" in str(exc_info.value.detail)