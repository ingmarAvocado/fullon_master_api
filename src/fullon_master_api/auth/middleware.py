"""
Authentication middleware for Fullon Master API.

This module provides middleware for JWT-based authentication
across all API endpoints.
"""

from typing import Callable, Optional

import jwt
from fastapi import HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param
from fullon_log import get_component_logger
from fullon_orm import DatabaseContext
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from ..config import settings
from .api_key_validator import ApiKeyValidator
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
                self.logger.info("User authenticated", user_id=user.uid, email=user.mail, path=request.url.path)
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


class JWTMiddleware(BaseHTTPMiddleware):
    """
    JWT authentication middleware for FastAPI.

    Validates JWT tokens on incoming requests and sets user data
    in request state for use in endpoints. Does not raise exceptions
    for invalid tokens - lets endpoints handle authentication errors.
    """

    def __init__(
        self,
        app,
        secret_key: str,
        algorithm: str = "HS256",
        exclude_paths: Optional[list[str]] = None
    ):
        """
        Initialize JWT middleware.

        Args:
            app: FastAPI application instance
            secret_key: Secret key for JWT validation
            algorithm: JWT algorithm (default: HS256)
            exclude_paths: List of paths to exclude from authentication
        """
        super().__init__(app)
        self.logger = get_component_logger("fullon.auth.jwt_middleware")
        self.jwt_handler = JWTHandler(secret_key, algorithm)
        self.api_key_validator = ApiKeyValidator()
        self.exclude_paths = exclude_paths or [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            f"{settings.api_prefix}/auth/login",
            f"{settings.api_prefix}/auth/verify"
        ]
        self.logger.info("JWT middleware initialized", excluded_paths_count=len(self.exclude_paths))

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Process incoming requests for JWT validation.

        Validates JWT token and loads User ORM from database,
        setting request.state.user if token is valid. Continues to endpoint
        regardless of token validity.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            HTTP response
        """
        # Check if path should be excluded from auth
        if self._is_excluded_path(request.url.path):
            self.logger.debug("Path excluded from JWT validation", path=request.url.path)
            return await call_next(request)

        # Extract token from Authorization header
        token = self._extract_token(request)

        if token:
            # Validate token using verify_token (returns payload or None)
            payload = self.jwt_handler.verify_token(token)

            if payload:
                # Extract user_id from payload and load User ORM from database
                user_id = payload.get("user_id")
                if user_id:
                    async with DatabaseContext() as db:
                        user = await db.users.get_by_id(user_id)
                        if user:
                            # Set User ORM instance (NOT dict)
                            request.state.user = user
                            self.logger.debug("User authenticated via JWT", user_id=user.uid, email=user.mail, path=request.url.path)
                            response = await call_next(request)
                            return response
                        else:
                            self.logger.warning("User not found in database", user_id=user_id, path=request.url.path)
                else:
                    self.logger.warning("Token missing user_id claim", path=request.url.path)
            else:
                self.logger.debug("JWT token invalid or expired", path=request.url.path)
        else:
            self.logger.debug("No JWT token provided", path=request.url.path)

        # Fallback to API key authentication
        api_key = self._extract_api_key(request)
        if api_key:
            user = await self.api_key_validator.validate_key(api_key)
            if user:
                # Set User ORM instance (same format as JWT auth)
                request.state.user = user
                self.logger.debug("User authenticated via API key", user_id=user.uid, email=user.mail, path=request.url.path)
                response = await call_next(request)
                return response

        # No valid authentication found - continue to endpoint (let endpoint handle auth requirement)
        response = await call_next(request)
        return response

    def _is_excluded_path(self, path: str) -> bool:
        """
        Check if a path should be excluded from JWT validation.

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

    def _extract_api_key(self, request: Request) -> Optional[str]:
        """
        Extract API key from request headers.

        Args:
            request: HTTP request

        Returns:
            API key string or None if not found
        """
        api_key_header = getattr(settings, 'api_key_header_name', 'X-API-Key')
        api_key = request.headers.get(api_key_header)
        return api_key


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
