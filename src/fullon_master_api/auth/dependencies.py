"""
FastAPI dependency injection for authentication.

This module provides reusable dependencies for authentication
and authorization in FastAPI endpoints.
"""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fullon_log import get_component_logger
from fullon_orm import DatabaseContext
from fullon_orm.models import User

from .jwt import JWTHandler, TokenData

# Module-level logger
logger = get_component_logger("fullon.auth.dependencies")


# Security scheme for JWT Bearer tokens
security = HTTPBearer()


class AuthDependencies:
    """Container for authentication dependencies."""

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """
        Initialize auth dependencies.

        Args:
            secret_key: Secret key for JWT validation
            algorithm: JWT algorithm (default: HS256)
        """
        self.jwt_handler = JWTHandler(secret_key, algorithm)

    async def get_current_user(
        self,
        credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
    ) -> User:
        """
        Dependency to get the current authenticated user.

        Args:
            credentials: Bearer token from Authorization header

        Returns:
            User ORM object from database

        Raises:
            HTTPException: If token is invalid or expired
        """
        token = credentials.credentials

        try:
            payload = self.jwt_handler.decode_token(token)
            username: str = payload.get("sub")
            if username is None:
                logger.error("Token missing 'sub' claim")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Fetch user from database using ORM
            async with DatabaseContext() as db:
                user = await db.users.get_by_email(username)
                if user is None:
                    logger.warning("User not found in database", username=username)
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User not found",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                logger.debug("User retrieved from database", username=username, uid=user.uid)
                return user
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            logger.error("Invalid token", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def get_current_active_user(
        self,
        current_user: Annotated[User, Depends(get_current_user)]
    ) -> User:
        """
        Dependency to get the current active user.

        Args:
            current_user: Current user from get_current_user dependency

        Returns:
            User ORM object if user is active

        Raises:
            HTTPException: If user is inactive
        """
        # Note: User model doesn't have 'disabled' field, could check other status fields
        # For now, return the user as-is
        logger.debug("Active user check", uid=current_user.uid)
        return current_user


async def get_current_user(request: Request) -> User:
    """
    FastAPI dependency to get the current authenticated user.

    This dependency assumes middleware has already validated the JWT
    and loaded the User ORM instance into request.state.user.

    Args:
        request: FastAPI request object

    Returns:
        User ORM object from request state

    Raises:
        HTTPException: If user is not authenticated
    """
    user = getattr(request.state, 'user', None)
    if user is None:
        logger.warning("User not authenticated")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.debug("User retrieved from request state", uid=user.uid, username=user.username)
    return user


def verify_token(token: str, secret_key: str) -> TokenData:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string
        secret_key: Secret key for decoding

    Returns:
        TokenData with user information

    Raises:
        HTTPException: If token is invalid
    """
    handler = JWTHandler(secret_key)

    try:
        payload = handler.decode_token(token)
        username: str = payload.get("sub")
        scopes: list = payload.get("scopes", [])
        logger.debug("Token verified", username=username, scopes_count=len(scopes))
        return TokenData(username=username, scopes=scopes)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
        logger.error("Token verification failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


class RequireScopes:
    """Dependency to require specific scopes for an endpoint."""

    def __init__(self, scopes: list[str]):
        """
        Initialize scope requirement.

        Args:
            scopes: List of required scopes
        """
        self.scopes = scopes

    def __call__(self, current_user: Annotated[User, Depends(get_current_user)]) -> User:
        """
        Check if user has required scopes.

        Args:
            current_user: Current authenticated user

        Returns:
            User ORM object if scopes are satisfied

        Raises:
            HTTPException: If user lacks required scopes
        """
        # Note: User model doesn't have scopes field yet
        # This would need to be implemented when user roles/scopes are added
        # For now, we'll log and return the user
        logger.debug("Scope check", uid=current_user.uid, required_scopes=self.scopes)

        # TODO: Implement scope checking when User model has scopes/roles
        # user_scopes = current_user.scopes or []
        # for required_scope in self.scopes:
        #     if required_scope not in user_scopes:
        #         logger.warning("Insufficient permissions", uid=current_user.uid, required_scope=required_scope)
        #         raise HTTPException(
        #             status_code=status.HTTP_403_FORBIDDEN,
        #             detail=f"Not enough permissions. Required scope: {required_scope}"
        #         )

        return current_user
