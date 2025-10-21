"""
Authentication module for Fullon Master API.

Provides JWT-based authentication and authorization for the unified API gateway.
"""

from .jwt import (
    JWTHandler,
    TokenData,
    create_access_token
)
from .middleware import (
    AuthMiddleware,
    create_auth_middleware
)
from .dependencies import (
    AuthDependencies,
    get_current_user,
    verify_token,
    RequireScopes,
    security
)

__all__ = [
    # JWT components
    "JWTHandler",
    "TokenData",
    "create_access_token",
    # Middleware
    "AuthMiddleware",
    "create_auth_middleware",
    # Dependencies
    "AuthDependencies",
    "get_current_user",
    "verify_token",
    "RequireScopes",
    "security"
]

# Package version
__version__ = "0.1.0"