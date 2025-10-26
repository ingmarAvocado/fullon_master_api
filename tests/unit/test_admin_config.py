"""
Unit tests for admin configuration settings.

Tests admin_mail configuration loading and validation.
"""
import pytest
from fullon_master_api.config import Settings


class TestAdminConfig:
    """Test admin configuration settings."""

    def test_default_admin_mail(self):
        """Test default admin email value."""
        settings = Settings()
        assert settings.admin_mail == "admin@fullon"

    def test_custom_admin_mail(self):
        """Test custom admin email via environment variable."""
        settings = Settings(admin_mail="custom-admin@example.com")
        assert settings.admin_mail == "custom-admin@example.com"

    def test_admin_mail_validation(self):
        """Test admin email validation (basic email format)."""
        # Valid emails
        valid_emails = [
            "admin@fullon",
            "admin@example.com",
            "test.admin@domain.co.uk",
            "admin+tag@domain.com",
        ]

        for email in valid_emails:
            settings = Settings(admin_mail=email)
            assert settings.admin_mail == email

    def test_admin_mail_empty_string(self):
        """Test that empty admin email is allowed (though not recommended)."""
        settings = Settings(admin_mail="")
        assert settings.admin_mail == ""

    @pytest.mark.parametrize(
        "invalid_email",
        [
            "admin",  # No @ symbol
            "@domain.com",  # No local part
            "admin@",  # No domain part
            "admin@.com",  # Invalid domain
        ],
    )
    def test_admin_mail_invalid_format(self, invalid_email):
        """Test that invalid email formats are accepted (no validation by default)."""
        # Note: Pydantic BaseSettings doesn't validate email format by default
        # Email validation would require EmailStr type hint
        settings = Settings(admin_mail=invalid_email)
        assert settings.admin_mail == invalid_email
