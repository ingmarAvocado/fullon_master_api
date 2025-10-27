"""
Integration tests for error handling in ORM endpoints.

Tests various failure scenarios and validates error responses.
"""
import pytest


@pytest.mark.asyncio
async def test_malformed_authorization_header(client):
    """Test handling of malformed Authorization header."""
    # Missing "Bearer " prefix
    headers = {"Authorization": "some_token"}
    response = client.get("/api/v1/orm/users/me", headers=headers)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_empty_authorization_header(client):
    """Test handling of empty Authorization header."""
    headers = {"Authorization": ""}
    response = client.get("/api/v1/orm/users/me", headers=headers)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_not_found_for_token(client, jwt_handler, db_context):
    """Test handling when token is valid but user doesn't exist."""
    from unittest.mock import patch, AsyncMock

    # Create token for non-existent user
    token = jwt_handler.create_token(
        {"sub": "nonexistent@example.com", "user_id": 999, "scopes": ["read"]}
    )

    # Mock the database to return None (user not found)
    with patch("fullon_master_api.auth.middleware.DatabaseContext") as mock_db_context:
        mock_db = AsyncMock()
        mock_db.users.get_by_id.return_value = None  # User not found
        mock_db_context.return_value.__aenter__.return_value = mock_db

        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/orm/users/me", headers=headers)

        # Should return 401 (user not found)
        assert response.status_code == 401
