"""
Integration tests for ORM endpoints with authentication.

Tests the complete flow:
1. JWT middleware validates token
2. Middleware sets request.state.user
3. ORM endpoint dependency gets user from request.state
4. ORM operation executes with authenticated user
5. Response returned to client
"""
import pytest


@pytest.mark.asyncio
async def test_get_current_user_with_valid_token(client, auth_headers, test_user):
    """
    Test GET /api/v1/orm/users/me with valid token.

    Expected flow:
    1. Request includes Bearer token
    2. JWT middleware validates token
    3. Middleware loads User from database
    4. Middleware sets request.state.user
    5. ORM endpoint gets user from request.state
    6. Returns user data
    """
    from unittest.mock import AsyncMock, patch

    # Mock the middleware's database call to get_by_id
    with patch('fullon_master_api.auth.middleware.DatabaseContext') as mock_db_context:
        mock_db = AsyncMock()
        mock_db.users.get_by_id.return_value = test_user
        mock_db_context.return_value.__aenter__.return_value = mock_db

        response = client.get("/api/v1/orm/users/me", headers=auth_headers)

        # Should return 200 OK
        assert response.status_code == 200

        # Response should contain user data (ORM API returns dict representation)
        user_data = response.json()
        assert isinstance(user_data, dict)
        assert "uid" in user_data
        assert "mail" in user_data
        assert user_data["mail"] == test_user.mail
        assert user_data["uid"] == test_user.uid


@pytest.mark.asyncio
async def test_get_current_user_without_token(client):
    """
    Test GET /api/v1/orm/users/me without authentication.

    Expected:
    - 401 Unauthorized
    - Error message about missing authentication
    """
    response = client.get("/api/v1/orm/users/me")

    # Should return 401 Unauthorized
    assert response.status_code == 401

    # Response should contain error message
    data = response.json()
    assert "detail" in data
    assert "authorization" in data["detail"].lower() or "authenticated" in data["detail"].lower()


@pytest.mark.asyncio
async def test_get_current_user_with_invalid_token(client):
    """
    Test GET /api/v1/orm/users/me with invalid token.

    Expected:
    - 401 Unauthorized
    - Error message about invalid token
    """
    invalid_headers = {"Authorization": "Bearer invalid_token_12345"}
    response = client.get("/api/v1/orm/users/me", headers=invalid_headers)

    # Should return 401 Unauthorized
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_with_expired_token(client, jwt_handler, test_user):
    """
    Test GET /api/v1/orm/users/me with expired token.

    Expected:
    - 401 Unauthorized
    - Error message about expired token
    """
    from datetime import timedelta

    # Create token that expires immediately
    expired_token = jwt_handler.create_token(
        {
            "sub": test_user.mail,
            "user_id": test_user.uid,
            "scopes": ["read", "write"]
        },
        expires_delta=timedelta(seconds=-1)  # Already expired
    )

    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/api/v1/orm/users/me", headers=headers)

    # Should return 401 Unauthorized
    assert response.status_code == 401

    # Response should indicate authentication failure
    data = response.json()
    assert "authenticated" in data["detail"].lower() or "authorization" in data["detail"].lower()


@pytest.mark.asyncio
async def test_list_users_requires_auth(client):
    """
    Test GET /api/v1/orm/users without authentication.

    Expected:
    - 401 Unauthorized
    """
    response = client.get("/api/v1/orm/users")

    # Should return 401 Unauthorized
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_users_with_auth(client, auth_headers):
    """
    Test GET /api/v1/orm/users with valid authentication.

    Note: This may require admin privileges depending on ORM API implementation.
    """
    response = client.get("/api/v1/orm/users", headers=auth_headers)

    # Should return 200 OK or 403 Forbidden (if not admin)
    assert response.status_code in [200, 403]

    if response.status_code == 200:
        users = response.json()
        assert isinstance(users, list)


@pytest.mark.asyncio
async def test_user_data_is_orm_model_not_dict(client, auth_headers):
    """
    Test that endpoint returns User ORM model data (not raw dict).

    Validates that dependency override correctly passes User model.
    """
    response = client.get("/api/v1/orm/users/me", headers=auth_headers)

    assert response.status_code == 200

    user_data = response.json()

    # User ORM model should have these fields
    required_fields = ["uid", "mail", "name"]
    for field in required_fields:
        assert field in user_data, f"Missing required field: {field}"
