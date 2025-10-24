"""
Unit tests for WebSocket JWT authentication.

Tests the authenticate_websocket function for various scenarios:
- Missing token
- Invalid token
- Expired token
- User not found
- Successful authentication
- Structured logging
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket
from fullon_master_api.websocket.auth import authenticate_websocket


@pytest.mark.asyncio
async def test_authenticate_websocket_missing_token():
    """Test WebSocket auth fails when no token is provided."""
    # Create mock WebSocket
    mock_ws = MagicMock(spec=WebSocket)
    mock_ws.query_params = {}  # No token
    mock_ws.client = "127.0.0.1:12345"
    mock_ws.url.path = "/api/v1/cache/ws/tickers/demo"
    mock_ws.close = AsyncMock()

    # Mock logger
    with patch('fullon_master_api.websocket.auth.logger') as mock_logger:
        result = await authenticate_websocket(mock_ws)

        assert result is False
        mock_ws.close.assert_called_once_with(code=1008, reason="Missing authentication token")
        mock_logger.warning.assert_called_once_with(
            "WebSocket auth failed: missing token",
            client="127.0.0.1:12345",
            path="/api/v1/cache/ws/tickers/demo"
        )


@pytest.mark.asyncio
async def test_authenticate_websocket_invalid_token():
    """Test WebSocket auth fails with invalid JWT token."""
    # Create mock WebSocket
    mock_ws = MagicMock(spec=WebSocket)
    mock_ws.query_params = {"token": "invalid.jwt.token"}
    mock_ws.client = "127.0.0.1:12345"
    mock_ws.url.path = "/api/v1/cache/ws/tickers/demo"
    mock_ws.close = AsyncMock()

    # Mock JWTHandler to raise exception
    with patch('fullon_master_api.websocket.auth.JWTHandler') as mock_jwt_class:
        mock_jwt = MagicMock()
        mock_jwt.validate_token.side_effect = Exception("Invalid token")
        mock_jwt_class.return_value = mock_jwt

        with patch('fullon_master_api.websocket.auth.logger') as mock_logger:
            result = await authenticate_websocket(mock_ws)

            assert result is False
            mock_ws.close.assert_called_once_with(code=1008, reason="Invalid authentication token")
            mock_logger.warning.assert_called_once_with(
                "WebSocket auth failed: invalid token",
                client="127.0.0.1:12345",
                path="/api/v1/cache/ws/tickers/demo",
                error="Invalid token"
            )


@pytest.mark.asyncio
async def test_authenticate_websocket_expired_token():
    """Test WebSocket auth fails with expired JWT token."""
    # Create mock WebSocket
    mock_ws = MagicMock(spec=WebSocket)
    mock_ws.query_params = {"token": "expired.jwt.token"}
    mock_ws.client = "127.0.0.1:12345"
    mock_ws.url.path = "/api/v1/cache/ws/tickers/demo"
    mock_ws.close = AsyncMock()

    # Mock JWTHandler to raise expired exception
    with patch('fullon_master_api.websocket.auth.JWTHandler') as mock_jwt_class:
        mock_jwt = MagicMock()
        mock_jwt.validate_token.side_effect = Exception("Token has expired")
        mock_jwt_class.return_value = mock_jwt

        with patch('fullon_master_api.websocket.auth.logger') as mock_logger:
            result = await authenticate_websocket(mock_ws)

            assert result is False
            mock_ws.close.assert_called_once_with(code=1008, reason="Invalid authentication token")
            mock_logger.warning.assert_called_once_with(
                "WebSocket auth failed: invalid token",
                client="127.0.0.1:12345",
                path="/api/v1/cache/ws/tickers/demo",
                error="Token has expired"
            )


@pytest.mark.asyncio
async def test_authenticate_websocket_user_not_found():
    """Test WebSocket auth fails when user from token doesn't exist."""
    # Create mock WebSocket
    mock_ws = MagicMock(spec=WebSocket)
    mock_ws.query_params = {"token": "valid.jwt.token"}
    mock_ws.client = "127.0.0.1:12345"
    mock_ws.url.path = "/api/v1/cache/ws/tickers/demo"
    mock_ws.close = AsyncMock()

    # Mock JWTHandler to return valid payload
    with patch('fullon_master_api.websocket.auth.JWTHandler') as mock_jwt_class:
        mock_jwt = MagicMock()
        mock_jwt.validate_token.return_value = {"user_id": 123, "username": "testuser"}
        mock_jwt_class.return_value = mock_jwt

        # Mock DatabaseContext - user not found
        with patch('fullon_master_api.websocket.auth.DatabaseContext') as mock_db_class:
            mock_db = AsyncMock()
            mock_db.users.get_by_id.return_value = None
            mock_db_class.return_value.__aenter__.return_value = mock_db
            mock_db_class.return_value.__aexit__.return_value = None

            with patch('fullon_master_api.websocket.auth.logger') as mock_logger:
                result = await authenticate_websocket(mock_ws)

                assert result is False
                mock_ws.close.assert_called_once_with(code=1008, reason="User not found")
                mock_logger.warning.assert_called_once_with(
                    "WebSocket auth failed: user not found",
                    user_id=123,
                    path="/api/v1/cache/ws/tickers/demo"
                )


@pytest.mark.asyncio
async def test_authenticate_websocket_database_error():
    """Test WebSocket auth fails on database error."""
    # Create mock WebSocket
    mock_ws = MagicMock(spec=WebSocket)
    mock_ws.query_params = {"token": "valid.jwt.token"}
    mock_ws.client = "127.0.0.1:12345"
    mock_ws.url.path = "/api/v1/cache/ws/tickers/demo"
    mock_ws.close = AsyncMock()

    # Mock JWTHandler to return valid payload
    with patch('fullon_master_api.websocket.auth.JWTHandler') as mock_jwt_class:
        mock_jwt = MagicMock()
        mock_jwt.validate_token.return_value = {"user_id": 123, "username": "testuser"}
        mock_jwt_class.return_value = mock_jwt

        # Mock DatabaseContext - database error
        with patch('fullon_master_api.websocket.auth.DatabaseContext') as mock_db_class:
            mock_db_class.return_value.__aenter__.side_effect = Exception(
                "Database connection failed"
            )
            mock_db_class.return_value.__aexit__.return_value = None

            with patch('fullon_master_api.websocket.auth.logger') as mock_logger:
                result = await authenticate_websocket(mock_ws)

                assert result is False
                mock_ws.close.assert_called_once_with(code=1008, reason="Authentication error")
                mock_logger.error.assert_called_once_with(
                    "WebSocket auth failed: database error",
                    user_id=123,
                    path="/api/v1/cache/ws/tickers/demo",
                    error="Database connection failed"
                )


@pytest.mark.asyncio
async def test_authenticate_websocket_success():
    """Test successful WebSocket authentication."""
    # Create mock WebSocket
    mock_ws = MagicMock(spec=WebSocket)
    mock_ws.query_params = {"token": "valid.jwt.token"}
    mock_ws.client = "127.0.0.1:12345"
    mock_ws.url.path = "/api/v1/cache/ws/tickers/demo"
    mock_ws.state = MagicMock()  # Mock state object

    # Mock User object
    mock_user = MagicMock()
    mock_user.uid = 123
    mock_user.name = "testuser"

    # Mock JWTHandler to return valid payload
    with patch('fullon_master_api.websocket.auth.JWTHandler') as mock_jwt_class:
        mock_jwt = MagicMock()
        mock_jwt.validate_token.return_value = {"user_id": 123, "username": "testuser"}
        mock_jwt_class.return_value = mock_jwt

        # Mock DatabaseContext - user found
        with patch('fullon_master_api.websocket.auth.DatabaseContext') as mock_db_class:
            mock_db = AsyncMock()
            mock_db.users.get_by_id.return_value = mock_user
            mock_db_class.return_value.__aenter__.return_value = mock_db
            mock_db_class.return_value.__aexit__.return_value = None

            with patch('fullon_master_api.websocket.auth.logger') as mock_logger:
                result = await authenticate_websocket(mock_ws)

                assert result is True
                assert mock_ws.state.user == mock_user
                mock_logger.info.assert_any_call(
                    "JWT token validated",
                    user_id=123,
                    path="/api/v1/cache/ws/tickers/demo"
                )
                mock_logger.info.assert_any_call(
                    "WebSocket authenticated successfully",
                    user_id=123,
                    username="testuser",
                    path="/api/v1/cache/ws/tickers/demo"
                )
