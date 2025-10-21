"""
FastAPI dependency injection for authentication.

This module provides reusable dependencies for authentication
and authorization in FastAPI endpoints.
"""

from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from .jwt import JWTHandler, TokenData


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
    ) -> dict:
        """
        Dependency to get the current authenticated user.

        Args:
            credentials: Bearer token from Authorization header

        Returns:
            User data from JWT payload

        Raises:
            HTTPException: If token is invalid or expired
        """
        token = credentials.credentials

        try:
            payload = self.jwt_handler.decode_token(token)
            username: str = payload.get("sub")
            if username is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def get_current_active_user(
        self,
        current_user: Annotated[dict, Depends(get_current_user)]
    ) -> dict:
        """
        Dependency to get the current active user.

        Args:
            current_user: Current user from get_current_user dependency

        Returns:
            User data if user is active

        Raises:
            HTTPException: If user is inactive
        """
        if current_user.get("disabled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        return current_user


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    secret_key: str
) -> dict:
    """
    Standalone dependency function to get current user.

    Args:
        credentials: Bearer token credentials
        secret_key: JWT secret key

    Returns:
        User data from token

    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    handler = JWTHandler(secret_key)

    try:
        payload = handler.decode_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


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
        return TokenData(username=username, scopes=scopes)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
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

    def __call__(self, current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
        """
        Check if user has required scopes.

        Args:
            current_user: Current authenticated user

        Returns:
            User data if scopes are satisfied

        Raises:
            HTTPException: If user lacks required scopes
        """
        user_scopes = current_user.get("scopes", [])

        for required_scope in self.scopes:
            if required_scope not in user_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not enough permissions. Required scope: {required_scope}"
                )

        return current_user