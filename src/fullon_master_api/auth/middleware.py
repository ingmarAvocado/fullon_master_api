"""
Authentication middleware for Fullon Master API.

This module provides middleware for JWT-based authentication
across all API endpoints.
"""

from typing import Optional, Callable
from fastapi import Request, HTTPException, status
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import jwt
from fullon_log import get_component_logger
from fullon_orm import DatabaseContext
from fullon_orm.models import User

from .jwt import JWTHandler


class AuthMiddleware(BaseHTTPMiddleware):
    """
    JWT authentication middleware for FastAPI.

    Validates JWT tokens on incoming requests and loads User ORM model
    from database, adding it to request state for use in endpoints.

    CRITICAL: Sets request.state.user as User ORM instance (NOT dict).
    """

    def __init__(
        self,
        app,
        secret_key: str,
        algorithm: str = "HS256",
        exclude_paths: Optional[list[str]] = None
    ):
        """
        Initialize authentication middleware.

        Args:
            app: FastAPI application instance
            secret_key: Secret key for JWT validation
            algorithm: JWT algorithm (default: HS256)
            exclude_paths: List of paths to exclude from authentication
        """
        super().__init__(app)
        self.logger = get_component_logger("fullon.auth.middleware")
        self.jwt_handler = JWTHandler(secret_key, algorithm)
        self.exclude_paths = exclude_paths or [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/auth/login",
            "/auth/register"
        ]
        self.logger.info("Auth middleware initialized", excluded_paths_count=len(self.exclude_paths))

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Process incoming requests for authentication.

        Validates JWT token, loads User ORM from database, and sets
        request.state.user with User instance for endpoint access.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            HTTP response

        Raises:
            HTTPException: 401 if token is missing, invalid, expired, or user not found
        """
        # Check if path should be excluded from auth
        if self._is_excluded_path(request.url.path):
            self.logger.debug("Path excluded from authentication", path=request.url.path)
            return await call_next(request)

        # Extract token from Authorization header
        token = self._extract_token(request)

        if not token:
            self.logger.warning("Missing authentication token", path=request.url.path, method=request.method)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            # Validate token and extract payload
            payload = self.jwt_handler.decode_token(token)
            user_id = payload.get("user_id")

            # Load User ORM instance from database (NOT dict from token)
            async with DatabaseContext() as db:
                user = await db.users.get_by_id(user_id)
                if user is None:
                    self.logger.warning("User not found in database", user_id=user_id, path=request.url.path)
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User not found",
                        headers={"WWW-Authenticate": "Bearer"},
                    )

                # Set User ORM instance (NOT dictionary)
                request.state.user = user
                self.logger.info("User authenticated", user_id=user.uid, username=user.username, path=request.url.path)
        except jwt.ExpiredSignatureError:
            self.logger.warning("Token expired", path=request.url.path)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            self.logger.error("Invalid token", path=request.url.path, error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Continue to next middleware/endpoint
        response = await call_next(request)
        return response

    def _is_excluded_path(self, path: str) -> bool:
        """
        Check if a path should be excluded from authentication.

        Args:
            path: Request path

        Returns:
            True if path should be excluded, False otherwise
        """
        # Exact match
        if path in self.exclude_paths:
            return True

        # Prefix match for paths like /static/*
        for excluded in self.exclude_paths:
            if excluded.endswith("*") and path.startswith(excluded[:-1]):
                return True

        return False

    def _extract_token(self, request: Request) -> Optional[str]:
        """
        Extract JWT token from request headers.

        Args:
            request: HTTP request

        Returns:
            JWT token string or None if not found
        """
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None

        scheme, token = get_authorization_scheme_param(authorization)
        if scheme.lower() != "bearer":
            return None

        return token


def create_auth_middleware(secret_key: str, **kwargs) -> AuthMiddleware:
    """
    Factory function to create auth middleware.

    Args:
        secret_key: JWT secret key
        **kwargs: Additional middleware configuration

    Returns:
        Configured AuthMiddleware instance
    """
    return lambda app: AuthMiddleware(app, secret_key, **kwargs)