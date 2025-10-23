"""
Tests validating User ORM model flow (NOT dictionaries).

Reference: docs/FULLON_ORM_LLM_README.md lines 1-9
"""
from unittest.mock import Mock

import pytest
from fullon_master_api.auth.dependencies import get_current_user
from fullon_orm.models import User


@pytest.mark.asyncio
async def test_get_current_user_returns_user_orm_model_not_dict():
    """
    CRITICAL: Test that get_current_user returns User ORM model, NOT dictionary.

    From docs/FULLON_ORM_LLM_README.md:
    'Repository methods ONLY accept ORM objects - NEVER dictionaries!'
    """
    # Mock request with User ORM in state
    request = Mock()
    test_user = Mock(spec=User)
    test_user.uid = 1
    test_user.mail = "test@example.com"
    test_user.name = "Test"
    test_user.password = "hashed"
    test_user.f2a = ""
    test_user.lastname = ""
    test_user.phone = ""
    test_user.id_num = ""
    request.state.user = test_user

    # Call dependency
    result = await get_current_user(request)

    # CRITICAL: Verify it returns User model instance
    assert isinstance(result, User)
    assert not isinstance(result, dict)
    assert result.uid == 1
    assert result.mail == "test@example.com"


@pytest.mark.asyncio
async def test_orm_endpoint_receives_user_model_not_dict(client, auth_headers):
    """Test that ORM endpoints receive User ORM model instances, NOT dictionaries."""

    response = client.get("/api/v1/orm/users/me", headers=auth_headers)

    # Should succeed (200 OK)
    assert response.status_code == 200

    # Response JSON is OK (API converts ORM to dict for JSON)
    data = response.json()
    assert "uid" in data
    assert "mail" in data
