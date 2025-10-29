"""
Unit tests for ApiKeyValidator.

Tests ApiKeyValidator.validate_key() method with various scenarios:
- Valid API key (with and without prefix)
- Key not found
- Inactive key
- Expired key
- Invalid format (too short)
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fullon_master_api.auth.api_key_validator import ApiKeyValidator
from fullon_orm.models import ApiKey, User


class TestApiKeyValidator:
    """Test cases for ApiKeyValidator."""

    @pytest.fixture
    def validator(self):
        """Create ApiKeyValidator instance."""
        return ApiKeyValidator()

    @pytest.fixture
    def mock_db_context(self):
        """Mock DatabaseContext."""
        return AsyncMock()

    @pytest.fixture
    def mock_user(self):
        """Mock User ORM instance."""
        user = MagicMock(spec=User)
        user.uid = 123
        user.mail = "test@example.com"
        user.username = "testuser"
        return user

    @pytest.fixture
    def mock_api_key(self, mock_user):
        """Mock ApiKey ORM instance."""
        api_key = MagicMock(spec=ApiKey)
        api_key.api_key_id = "test-key-id"
        api_key.uid = mock_user.uid
        api_key.key = "fullon_ak_test_key_123"
        api_key.is_active = True
        api_key.expires_at = None
        api_key.last_used_at = None
        return api_key

    @pytest.mark.asyncio
    async def test_validate_key_user_not_found(self, validator, mock_db_context, mock_api_key):
        """Test validation when associated user is not found."""
        # Setup mocks
        mock_db_context.api_keys.get_by_key.return_value = mock_api_key
        mock_db_context.users.get_by_id.return_value = None  # User not found
        mock_db_context.api_keys.update_last_used = AsyncMock()

        with patch('fullon_master_api.auth.api_key_validator.DatabaseContext') as mock_context_class:
            mock_context_instance = AsyncMock()
            mock_context_instance.__aenter__.return_value = mock_db_context
            mock_context_instance.__aexit__.return_value = None
            mock_context_class.return_value = mock_context_instance

            # Execute validation
            result = await validator.validate_key("fullon_ak_test_key_123")

            # Assertions
            assert result is None
            mock_db_context.api_keys.get_by_key.assert_called_once_with("fullon_ak_test_key_123")
            mock_db_context.users.get_by_id.assert_called_once_with(mock_api_key.uid)
            mock_db_context.api_keys.update_last_used.assert_not_called()  # Should not update if user not found

    def test_validate_key_invalid_format_too_short(self, validator):
        """Test validation with invalid format (too short)."""
        result = validator._validate_format("short")
        assert result is False

    def test_validate_key_valid_format_with_prefix(self, validator):
        """Test validation with valid format (with prefix)."""
        result = validator._validate_format("fullon_ak_valid_key_123456789")
        assert result is True

    def test_validate_key_valid_format_without_prefix(self, validator):
        """Test validation with valid format (without prefix)."""
        result = validator._validate_format("valid_key_without_prefix_12345")
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_key_returns_user_orm_instance(self, validator, mock_db_context, mock_user, mock_api_key):
        """Test that validation returns User ORM instance."""
        # Setup mocks
        mock_db_context.api_keys.get_by_key.return_value = mock_api_key
        mock_db_context.users.get_by_id.return_value = mock_user
        mock_db_context.api_keys.update_last_used = AsyncMock()

        with patch('fullon_master_api.auth.api_key_validator.DatabaseContext') as mock_context_class:
            mock_context_instance = AsyncMock()
            mock_context_instance.__aenter__.return_value = mock_db_context
            mock_context_instance.__aexit__.return_value = None
            mock_context_class.return_value = mock_context_instance

            # Execute validation
            result = await validator.validate_key("fullon_ak_test_key_123")

            # Assertions
            assert result == mock_user
            assert isinstance(result, type(mock_user))  # Should be User ORM instance

    @pytest.mark.asyncio
    async def test_validate_key_not_found(self, validator, mock_db_context):
        """Test validation when API key is not found in database."""
        # Setup mocks
        mock_db_context.api_keys.get_by_key.return_value = None  # Key not found
        mock_db_context.api_keys.update_last_used = AsyncMock()

        with patch('fullon_master_api.auth.api_key_validator.DatabaseContext') as mock_context_class:
            mock_context_instance = AsyncMock()
            mock_context_instance.__aenter__.return_value = mock_db_context
            mock_context_instance.__aexit__.return_value = None
            mock_context_class.return_value = mock_context_instance

            # Execute validation
            result = await validator.validate_key("fullon_ak_nonexistent_key")

            # Assertions
            assert result is None
            mock_db_context.api_keys.get_by_key.assert_called_once_with("fullon_ak_nonexistent_key")
            mock_db_context.users.get_by_id.assert_not_called()  # Should not proceed to user lookup
            mock_db_context.api_keys.update_last_used.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_key_inactive(self, validator, mock_db_context, mock_user, mock_api_key):
        """Test validation when API key is inactive."""
        # Setup mocks
        mock_api_key.is_active = False
        mock_db_context.api_keys.get_by_key.return_value = mock_api_key
        mock_db_context.users.get_by_id.return_value = mock_user
        mock_db_context.api_keys.update_last_used = AsyncMock()

        with patch('fullon_master_api.auth.api_key_validator.DatabaseContext') as mock_context_class:
            mock_context_instance = AsyncMock()
            mock_context_instance.__aenter__.return_value = mock_db_context
            mock_context_instance.__aexit__.return_value = None
            mock_context_class.return_value = mock_context_instance

            # Execute validation
            result = await validator.validate_key("fullon_ak_test_key_123")

            # Assertions
            assert result is None
            mock_db_context.api_keys.get_by_key.assert_called_once_with("fullon_ak_test_key_123")
            mock_db_context.users.get_by_id.assert_not_called()  # Should not proceed to user lookup
            mock_db_context.api_keys.update_last_used.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_key_expired(self, validator, mock_db_context, mock_user, mock_api_key):
        """Test validation when API key has expired."""
        # Setup mocks
        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_api_key.expires_at = expired_time
        mock_db_context.api_keys.get_by_key.return_value = mock_api_key
        mock_db_context.users.get_by_id.return_value = mock_user
        mock_db_context.api_keys.update_last_used = AsyncMock()

        with patch('fullon_master_api.auth.api_key_validator.DatabaseContext') as mock_context_class:
            mock_context_instance = AsyncMock()
            mock_context_instance.__aenter__.return_value = mock_db_context
            mock_context_instance.__aexit__.return_value = None
            mock_context_class.return_value = mock_context_instance

            # Execute validation
            result = await validator.validate_key("fullon_ak_test_key_123")

            # Assertions
            assert result is None
            mock_db_context.api_keys.get_by_key.assert_called_once_with("fullon_ak_test_key_123")
            mock_db_context.users.get_by_id.assert_not_called()  # Should not proceed to user lookup
            mock_db_context.api_keys.update_last_used.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_key_valid(self, validator, mock_db_context, mock_user, mock_api_key):
        """Test validation with a fully valid API key."""
        # Setup mocks
        mock_db_context.api_keys.get_by_key.return_value = mock_api_key
        mock_db_context.users.get_by_id.return_value = mock_user
        mock_db_context.api_keys.update_last_used = AsyncMock()

        with patch('fullon_master_api.auth.api_key_validator.DatabaseContext') as mock_context_class:
            mock_context_instance = AsyncMock()
            mock_context_instance.__aenter__.return_value = mock_db_context
            mock_context_instance.__aexit__.return_value = None
            mock_context_class.return_value = mock_context_instance

            # Execute validation
            result = await validator.validate_key("fullon_ak_test_key_123")

            # Assertions
            assert result == mock_user
            mock_db_context.api_keys.get_by_key.assert_called_once_with("fullon_ak_test_key_123")
            mock_db_context.users.get_by_id.assert_called_once_with(mock_api_key.uid)
            mock_db_context.api_keys.update_last_used.assert_called_once_with(mock_api_key.api_key_id)
