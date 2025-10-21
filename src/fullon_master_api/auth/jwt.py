"""
JWT authentication module for Fullon Master API.

This module handles JWT token creation, validation, and management
for the unified API gateway.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from pydantic import BaseModel
from fullon_log import get_component_logger


class JWTHandler:
    """Handles JWT token operations."""

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """
        Initialize JWT handler.

        Args:
            secret_key: Secret key for JWT encoding/decoding
            algorithm: Algorithm to use for JWT (default: HS256)
        """
        self.logger = get_component_logger("fullon.auth.jwt")
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.logger.info("JWT handler initialized", algorithm=algorithm)

    def create_token(
        self,
        payload: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT token.

        Args:
            payload: Data to encode in the token
            expires_delta: Token expiration time delta

        Returns:
            Encoded JWT token string
        """
        to_encode = payload.copy()

        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            # Default expiration: 24 hours
            expire = datetime.now(timezone.utc) + timedelta(hours=24)

        to_encode.update({"exp": expire})

        encoded_jwt = jwt.encode(
            to_encode,
            self.secret_key,
            algorithm=self.algorithm
        )
        self.logger.info("Token created", subject=payload.get("sub"), expires_at=expire.isoformat())
        return encoded_jwt

    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        Decode and validate a JWT token.

        Args:
            token: JWT token string to decode

        Returns:
            Decoded payload dictionary

        Raises:
            jwt.ExpiredSignatureError: If token has expired
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            self.logger.debug("Token decoded successfully", subject=payload.get("sub"))
            return payload
        except jwt.ExpiredSignatureError:
            self.logger.warning("Token expired", token_prefix=token[:10] if token else "")
            raise
        except jwt.InvalidTokenError as e:
            self.logger.error("Invalid token", error=str(e))
            raise

    def verify_token(self, token: str) -> bool:
        """
        Verify if a token is valid.

        Args:
            token: JWT token to verify

        Returns:
            True if token is valid, False otherwise
        """
        try:
            self.decode_token(token)
            self.logger.debug("Token verified successfully")
            return True
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            self.logger.debug("Token verification failed")
            return False


class TokenData(BaseModel):
    """Model for token data."""
    username: Optional[str] = None
    scopes: list[str] = []


def create_access_token(
    data: dict,
    secret_key: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create an access token.

    Args:
        data: Data to encode in the token
        secret_key: Secret key for encoding
        expires_delta: Token expiration time

    Returns:
        Encoded JWT token
    """
    handler = JWTHandler(secret_key)
    return handler.create_token(data, expires_delta)