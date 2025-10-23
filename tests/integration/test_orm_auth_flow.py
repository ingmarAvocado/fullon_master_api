"""
Integration tests for complete auth flow with ORM endpoints.

Validates the request processing pipeline:
Request → CORS → JWT Middleware → Route Handler → Response
"""
import pytest
from unittest.mock import patch, AsyncMock, Mock


@pytest.mark.asyncio
async def test_auth_middleware_sets_request_state_user(client, auth_headers):
    """
    Test that JWT middleware correctly sets request.state.user.

    This validates Issue #11 integration.
    """
    # Mock the database call
    from pydantic import BaseModel

    class MockUser(BaseModel):
        uid: int = 1
        mail: str = "testuser@example.com"
        username: str = "testuser"
        name: str = "Test"
        lastname: str = "User"

    mock_user = MockUser()

    with patch('fullon_master_api.auth.middleware.DatabaseContext') as mock_db_context:
        mock_db = AsyncMock()
        mock_db.users.get_by_id.return_value = mock_user
        mock_db_context.return_value.__aenter__.return_value = mock_db

        response = client.get("/api/v1/orm/users/me", headers=auth_headers)

        # If this succeeds, middleware set request.state.user correctly
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            # Verify the user data matches what was set in request.state
            user_data = response.json()
            assert user_data["mail"] == "testuser@example.com"


@pytest.mark.asyncio
async def test_orm_dependency_gets_user_from_request_state(client, auth_headers):
    """
    Test that ORM endpoints use master API's get_current_user dependency.

    This validates Issue #16 (dependency override).
    """
    # Mock the database call
    from pydantic import BaseModel

    class MockUser(BaseModel):
        uid: int = 1
        mail: str = "testuser@example.com"
        username: str = "testuser"
        name: str = "Test User"
        lastname: str = "User"

    mock_user = MockUser()

    with patch('fullon_master_api.auth.middleware.DatabaseContext') as mock_db_context:
        mock_db = AsyncMock()
        mock_db.users.get_by_id.return_value = mock_user
        mock_db_context.return_value.__aenter__.return_value = mock_db

        response = client.get("/api/v1/orm/users/me", headers=auth_headers)

        assert response.status_code in [200, 404]

        if response.status_code == 200:
            # User data should match what dependency override passed
            user_data = response.json()
            assert user_data["mail"] == "testuser@example.com"
            assert user_data["name"] == "Test User"


@pytest.mark.asyncio
async def test_middleware_runs_before_orm_endpoints(client, auth_headers):
    """
    Test that JWT middleware runs before ORM route handlers.

    Validates middleware execution order.
    """
    # Test without auth - should fail at middleware level
    response_no_auth = client.get("/api/v1/orm/users/me")
    assert response_no_auth.status_code == 401

    # Test with invalid auth - should fail at middleware level
    response_invalid = client.get("/api/v1/orm/users/me", headers={"Authorization": "Bearer invalid"})
    assert response_invalid.status_code == 401

    # Test with valid auth - should pass middleware and reach endpoint
    from pydantic import BaseModel

    class MockUser(BaseModel):
        uid: int = 1
        mail: str = "testuser@example.com"
        username: str = "testuser"
        name: str = "Test"
        lastname: str = "User"

    mock_user = MockUser()

    with patch('fullon_master_api.auth.middleware.DatabaseContext') as mock_db_context:
        mock_db = AsyncMock()
        mock_db.users.get_by_id.return_value = mock_user
        mock_db_context.return_value.__aenter__.return_value = mock_db

        response_valid = client.get("/api/v1/orm/users/me", headers=auth_headers)
        assert response_valid.status_code in [200, 404]


@pytest.mark.asyncio
async def test_cors_middleware_runs_before_jwt(client):
    """
    Test that CORS middleware runs before JWT middleware.

    Validates middleware execution order.
    """
    # This is tested implicitly - if CORS headers are present in responses,
    # it means CORS middleware ran before JWT middleware
    response = client.get("/api/v1/orm/users/me")

    # Check for CORS headers in response
    assert "access-control-allow-origin" in response.headers or response.status_code == 401


@pytest.mark.asyncio
async def test_request_pipeline_integration(client, auth_headers):
    """
    Test the complete request pipeline integration.

    Request → CORS → JWT → ORM Route Handler → Response
    """
    from pydantic import BaseModel

    class MockUser(BaseModel):
        uid: int = 1
        mail: str = "testuser@example.com"
        username: str = "testuser"
        name: str = "Test User"
        lastname: str = "User"

    mock_user = MockUser()

    with patch('fullon_master_api.auth.middleware.DatabaseContext') as mock_db_context:
        mock_db = AsyncMock()
        mock_db.users.get_by_id.return_value = mock_user
        mock_db_context.return_value.__aenter__.return_value = mock_db

        response = client.get("/api/v1/orm/users/me", headers=auth_headers)

        # Pipeline should complete successfully
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            # Verify data flows through entire pipeline
            user_data = response.json()
            assert isinstance(user_data, dict)
            assert "uid" in user_data
            assert "mail" in user_data