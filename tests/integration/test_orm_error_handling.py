"""
Integration tests for error handling in ORM endpoints.

Tests various failure scenarios and validates error responses.
"""
import pytest
from unittest.mock import patch, AsyncMock


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
async def test_user_not_found_for_token(client, jwt_handler):
    """Test handling when token is valid but user doesn't exist."""
    # Create token for non-existent user
    token = jwt_handler.generate_token(
        user_id=999,  # Non-existent user ID
        username="nonexistent@example.com"
    )

    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/orm/users/me", headers=headers)

    # Should return 401 (user not found)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_database_connection_error(client, auth_headers):
    """Test handling of database connection errors."""
    # Mock database context to raise an exception
    with patch('fullon_master_api.auth.middleware.DatabaseContext') as mock_db_context:
        mock_db_context.return_value.__aenter__.side_effect = Exception("Database connection failed")

        response = client.get("/api/v1/orm/users/me", headers=auth_headers)

        # Should return 500 or 401 depending on error handling
        assert response.status_code in [401, 500]


@pytest.mark.asyncio
async def test_malformed_jwt_token(client):
    """Test handling of malformed JWT tokens."""
    headers = {"Authorization": "Bearer not.a.jwt.token"}
    response = client.get("/api/v1/orm/users/me", headers=headers)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_handling(client, jwt_handler):
    """Test handling of expired tokens."""
    from datetime import timedelta

    # Create token that expires immediately
    expired_token = jwt_handler.create_token(
        payload={"sub": "testuser@example.com", "user_id": 1, "username": "testuser@example.com"},
        expires_delta=timedelta(seconds=-1)  # Already expired
    )

    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/api/v1/orm/users/me", headers=headers)

    # Should return 401 Unauthorized
    assert response.status_code == 401

    # Response should mention expiration
    data = response.json()
    assert "expired" in data["detail"].lower() or "invalid" in data["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_token_signature(client):
    """Test handling of tokens with invalid signatures."""
    # Create a token with invalid signature (just random string)
    headers = {"Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0dXNlckBleGFtcGxlLmNvbSIsInNjb3BlcyI6WyJyZWFkIiwid3JpdGUiXX0.invalid_signature"}
    response = client.get("/api/v1/orm/users/me", headers=headers)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_token_claims(client, jwt_handler):
    """Test handling of tokens missing required claims."""
    # Create token without 'sub' claim
    import jwt
    from fullon_master_api.config import settings

    payload = {
        "scopes": ["read", "write"]
        # Missing 'sub' claim
    }

    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/orm/users/me", headers=headers)

    assert response.status_code == 401