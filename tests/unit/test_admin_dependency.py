"""
Unit tests for admin user dependency.

Tests get_admin_user() dependency for authentication and authorization.
"""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fullon_master_api.auth.dependencies import get_admin_user
from fullon_master_api.config import settings


class MockUser:
    """Mock user for testing."""

    def __init__(self, uid: int, mail: str):
        self.uid = uid
        self.mail = mail


class TestAdminDependency:
    """Test admin user dependency."""

    @pytest.mark.asyncio
    async def test_admin_user_success(self):
        """Test successful admin user authentication."""
        admin_user = MockUser(uid=1, mail=settings.admin_mail)
        mock_request = MagicMock()
        mock_request.state = type("State", (), {"user": admin_user})()

        result = await get_admin_user(mock_request)

        assert result == admin_user
        assert result.mail == settings.admin_mail

    @pytest.mark.asyncio
    async def test_non_authenticated_user_401(self):
        """Test 401 error for non-authenticated user."""
        mock_request = MagicMock()
        mock_request.state = type("State", (), {})()  # No user in state

        with pytest.raises(HTTPException) as exc_info:
            await get_admin_user(mock_request)

        assert exc_info.value.status_code == 401
        assert "Not authenticated" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_non_admin_user_403(self):
        """Test 403 error for authenticated but non-admin user."""
        non_admin_user = MockUser(uid=2, mail="user@example.com")
        mock_request = MagicMock()
        mock_request.state = type("State", (), {"user": non_admin_user})()

        with pytest.raises(HTTPException) as exc_info:
            await get_admin_user(mock_request)

        assert exc_info.value.status_code == 403
        assert "Admin access required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_different_admin_email(self):
        """Test with different admin email configuration."""
        from unittest.mock import patch

        # Create new settings instance with different admin email
        from fullon_master_api.config import Settings

        custom_settings = Settings(admin_mail="custom-admin@test.com")

        # Mock user with custom admin email
        admin_user = MockUser(uid=1, mail="custom-admin@test.com")
        mock_request = MagicMock()
        mock_request.state = type("State", (), {"user": admin_user})()

        # Patch the config.settings that gets imported in get_admin_user
        with patch("fullon_master_api.config.settings", custom_settings):
            result = await get_admin_user(mock_request)
            assert result.mail == "custom-admin@test.com"

    @pytest.mark.asyncio
    async def test_case_sensitive_email_matching(self):
        """Test that email matching is case-sensitive."""
        # Admin email is "admin@fullon" (lowercase)
        non_admin_user = MockUser(uid=2, mail="ADMIN@FULLON")  # Uppercase
        mock_request = MagicMock()
        mock_request.state = type("State", (), {"user": non_admin_user})()

        with pytest.raises(HTTPException) as exc_info:
            await get_admin_user(mock_request)

        assert exc_info.value.status_code == 403
        assert "Admin access required" in exc_info.value.detail
