"""
JWT authentication module for Fullon Master API.

This module handles JWT token creation, validation, and management
for the unified API gateway.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fullon_log import get_component_logger
from pydantic import BaseModel

from ..config import settings


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

    def generate_token(self, user_id: int, username: str, email: Optional[str] = None) -> str:
        """
        Generate a JWT access token for a user.

        Args:
            user_id: User's unique identifier
            username: User's username
            email: User's email address (optional)

        Returns:
            Encoded JWT token string
        """
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiration_minutes)

        payload = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "exp": expire,
        }

        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        self.logger.info("JWT token generated", user_id=user_id)
        return token

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
            jwt.PyJWTError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm]
            )
            self.logger.debug("Token decoded successfully", user_id=payload.get("user_id"))
            return payload
        except jwt.PyJWTError as e:
            self.logger.warning("Token decode failed", error=str(e))
            raise

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify if a token is valid and return its payload.

        Args:
            token: JWT token to verify

        Returns:
            Decoded payload dictionary if token is valid, None otherwise
        """
        try:
            payload = self.decode_token(token)
            self.logger.debug("Token verified successfully", user_id=payload.get("user_id"))
            return payload
        except jwt.PyJWTError as e:
            reason = "expired" if isinstance(e, jwt.ExpiredSignatureError) else "invalid"
            self.logger.warning("Token verification failed", reason=reason)
            return None


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


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string
    """
    import bcrypt
    # Generate salt and hash password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')
