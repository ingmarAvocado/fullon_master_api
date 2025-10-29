"""
API Key Authentication Validator for Fullon Master API.

This module provides validation logic for API keys, including format checking,
database lookup, expiration validation, and user association.
"""

from datetime import datetime, timezone
from typing import Optional

from fullon_log import get_component_logger
from fullon_orm import DatabaseContext
from fullon_orm.models import User

logger = get_component_logger("fullon.auth.api_key_validator")


class ApiKeyValidator:
    """Validates API keys and loads associated users."""

    async def validate_key(self, key: str) -> Optional[User]:
        """
        Validate API key and return associated User ORM instance.

        Steps:
        1. Validate key format (minimum length check)
        2. Query database using db.api_keys.get_by_key(key)
        3. Check is_active flag
        4. Check expiration (expires_at > now or null)
        5. Update last_used_at timestamp
        6. Load and return associated User ORM instance

        Args:
            key: API key string to validate

        Returns:
            User ORM instance if valid, None otherwise
        """
        # Step 1: Validate format
        if not self._validate_format(key):
            return None

        async with DatabaseContext() as db:
            # Step 2: Query database
            api_key = await db.api_keys.get_by_key(key)
            if api_key is None:
                logger.warning(
                    "API key not found in database",
                    key_prefix=key[:13] + "***"
                )
                return None

            # Step 3: Check active status
            if not api_key.is_active:
                logger.warning(
                    "API key is inactive",
                    key_prefix=key[:13] + "***",
                    key_id=api_key.api_key_id
                )
                return None

            # Step 4: Check expiration
            now = datetime.now(timezone.utc)
            if api_key.expires_at is not None:
                # Handle both timezone-aware and timezone-naive expires_at
                expires_at = api_key.expires_at
                if expires_at.tzinfo is None:
                    # expires_at is timezone-naive, assume UTC
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at <= now:
                    logger.warning(
                        "API key has expired",
                        key_prefix=key[:13] + "***",
                        key_id=api_key.api_key_id,
                        expires_at=api_key.expires_at.isoformat()
                    )
                    return None

            # Step 5: Load associated User
            user = await db.users.get_by_id(api_key.uid)
            if user is None:
                logger.error(
                    "Associated user not found for API key",
                    key_prefix=key[:13] + "***",
                    key_id=api_key.api_key_id,
                    user_id=api_key.uid
                )
                return None

            # Step 6: Update last_used_at (only after all validations pass)
            await db.api_keys.update_last_used(api_key.api_key_id)

            logger.info(
                "API key validation successful",
                key_prefix=key[:13] + "***",
                user_id=user.uid,
                key_id=api_key.api_key_id
            )

            return user

    def _validate_format(self, key: str) -> bool:
        """
        Validate API key format before database lookup.

        Args:
            key: API key string to validate

        Returns:
            True if format is valid, False otherwise
        """
        if len(key) < 10:  # Minimum token length
            logger.warning(
                "API key too short",
                length=len(key)
            )
            return False

        return True
