"""
WebSocket JWT Authentication Handler.

Validates JWT tokens passed as query parameters for WebSocket connections.
Follows ADR-002: WebSocket Proxy for Cache API.
"""
from fastapi import WebSocket
from fullon_log import get_component_logger
from fullon_orm import DatabaseContext

from ..auth.jwt import JWTHandler
from ..config import settings

logger = get_component_logger("fullon.master_api.websocket.auth")


async def authenticate_websocket(websocket: WebSocket) -> bool:
    """
    Authenticate WebSocket connection via query parameter token.

    Args:
        websocket: FastAPI WebSocket connection

    Returns:
        bool: True if authenticated, False if rejected

    Side Effects:
        - Sets websocket.state.user to User model if authenticated
        - Closes websocket with code 1008 if authentication fails

    Authentication Flow:
        1. Extract 'token' from query parameters
        2. Validate JWT using existing JWTHandler
        3. Load User from database using user_id from token
        4. Store User model in websocket.state.user
        5. Log auth success/failure with structured logging

    Query Parameter Format:
        ws://host/api/v1/cache/ws/tickers/demo?token=jwt_token_here

    Error Codes:
        1008 (Policy Violation): Missing token, invalid token, or user not found
    """
    # Extract token from query params
    token = websocket.query_params.get("token")

    if not token:
        logger.warning(
            "WebSocket auth failed: missing token",
            client=str(websocket.client),
            path=websocket.url.path
        )
        await websocket.close(code=1008, reason="Missing authentication token")
        return False

    # Validate JWT token
    try:
        jwt_handler = JWTHandler(
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm
        )
        payload = jwt_handler.validate_token(token)

        # Extract user_id from token payload
        user_id = int(payload["user_id"])

        logger.info(
            "JWT token validated",
            user_id=user_id,
            path=websocket.url.path
        )

    except Exception as e:
        logger.warning(
            "WebSocket auth failed: invalid token",
            client=str(websocket.client),
            path=websocket.url.path,
            error=str(e)
        )
        await websocket.close(code=1008, reason="Invalid authentication token")
        return False

    # Load User model from database
    try:
        async with DatabaseContext() as db:
            user = await db.users.get_by_id(user_id)

            if not user:
                logger.warning(
                    "WebSocket auth failed: user not found",
                    user_id=user_id,
                    path=websocket.url.path
                )
                await websocket.close(code=1008, reason="User not found")
                return False

        # Store User model in websocket state for downstream use
        websocket.state.user = user

        logger.info(
            "WebSocket authenticated successfully",
            user_id=user_id,
            username=user.name,
            path=websocket.url.path
        )
        return True

    except Exception as e:
        logger.error(
            "WebSocket auth failed: database error",
            user_id=user_id,
            path=websocket.url.path,
            error=str(e)
        )
        await websocket.close(code=1008, reason="Authentication error")
        return False
