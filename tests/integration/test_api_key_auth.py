"""
Integration tests for API key authentication.

Tests dual authentication middleware (JWT + API key) with real database and HTTP requests.
"""

import pytest
from datetime import datetime, timezone, timedelta

from fullon_orm.models import User

from tests.conftest import TestDatabaseContext


class TestApiKeyAuthIntegration:
    """Integration tests for API key authentication."""

    @pytest.fixture
    async def test_user(self, db_context: TestDatabaseContext) -> User:
        """Create a test user for authentication tests."""
        import uuid
        # Create test user with unique email
        unique_id = str(uuid.uuid4())[:8]
        user = User(
            mail=f"test_api_key_{unique_id}@example.com",
            password="hashed_password",
            f2a="",
            name="Test",
            lastname="User",
            phone="",
            id_num=""
        )
        user = await db_context.users.add_user(user)
        return user

    @pytest.fixture
    async def test_api_key(self, db_context: TestDatabaseContext, test_user: User):
        """Create a test API key for the test user."""
        import uuid
        from fullon_orm.models import ApiKey

        # Create API key with unique key
        unique_id = str(uuid.uuid4())[:8]
        api_key = ApiKey(
            uid=test_user.uid,
            key=f"fullon_ak_test_integration_key_{unique_id}",
            name="Test Integration Key",
            description="Key for integration tests",
            scopes='["read", "write"]',
            is_active=True,
            expires_at=None
        )

        api_key = await db_context.api_keys.add(api_key)
        return api_key

    @pytest.fixture
    async def expired_api_key(self, db_context: TestDatabaseContext, test_user: User):
        """Create an expired API key for testing."""
        import uuid
        from fullon_orm.models import ApiKey

        # Create expired API key
        unique_id = str(uuid.uuid4())[:8]
        past_time = datetime.now() - timedelta(hours=1)
        api_key = ApiKey(
            uid=test_user.uid,
            key=f"fullon_ak_expired_test_key_{unique_id}",
            name="Expired Test Key",
            description="Expired key for testing",
            scopes='["read"]',
            is_active=True,
            expires_at=past_time
        )

        api_key = await db_context.api_keys.add(api_key)
        return api_key

    @pytest.fixture
    async def inactive_api_key(self, db_context: TestDatabaseContext, test_user: User):
        """Create an inactive API key for testing."""
        import uuid
        from fullon_orm.models import ApiKey

        # Create inactive API key
        unique_id = str(uuid.uuid4())[:8]
        api_key = ApiKey(
            uid=test_user.uid,
            key=f"fullon_ak_inactive_test_key_{unique_id}",
            name="Inactive Test Key",
            description="Inactive key for testing",
            scopes='["read"]',
            is_active=False,
            expires_at=None
        )

        api_key = await db_context.api_keys.add(api_key)
        return api_key

    def test_api_key_authentication_success(
        self,
        client,
        test_user: User,
        test_api_key
    ):
        """Test successful API key authentication."""
        # Make request with API key
        response = client.get(
            "/api/v1/orm/users/me",
            headers={"X-API-Key": test_api_key.key}
        )

        assert response.status_code == 200
        user_data = response.json()
        assert user_data["uid"] == test_user.uid
        assert user_data["mail"] == test_user.mail

    def test_api_key_authentication_expired_key(
        self,
        client,
        expired_api_key
    ):
        """Test API key authentication with expired key."""
        # Make request with expired API key
        response = client.get(
            "/api/v1/orm/users/me",
            headers={"X-API-Key": expired_api_key.key}
        )

        # Should be rejected with 401
        assert response.status_code == 401

    def test_api_key_authentication_inactive_key(
        self,
        client,
        inactive_api_key
    ):
        """Test API key authentication with inactive key."""
        # Make request with inactive API key
        response = client.get(
            "/api/v1/orm/users/me",
            headers={"X-API-Key": inactive_api_key.key}
        )

        # Should be rejected with 401
        assert response.status_code == 401

    def test_api_key_authentication_invalid_key(self, client):
        """Test API key authentication with invalid key."""
        # Make request with invalid API key
        response = client.get(
            "/api/v1/orm/users/me",
            headers={"X-API-Key": "invalid_key_without_prefix"}
        )

        # Should be rejected with 401
        assert response.status_code == 401

    def test_jwt_authentication_still_works(
        self,
        client,
        auth_headers,
        test_user: User
    ):
        """Test that JWT authentication still works after API key implementation."""
        # Make authenticated request with JWT
        response = client.get(
            "/api/v1/orm/users/me",
            headers=auth_headers
        )

        assert response.status_code == 200
        user_data = response.json()
        assert user_data["uid"] == test_user.uid

    def test_both_auth_methods_set_same_user_format(
        self,
        client,
        auth_headers,
        test_user: User,
        test_api_key
    ):
        """Test that both auth methods set request.state.user in identical format."""
        # Test with API key
        api_key_response = client.get(
            "/api/v1/orm/users/me",
            headers={"X-API-Key": test_api_key.key}
        )

        assert api_key_response.status_code == 200
        api_key_user_data = api_key_response.json()

        # Test with JWT
        jwt_response = client.get(
            "/api/v1/orm/users/me",
            headers=auth_headers
        )

        assert jwt_response.status_code == 200
        jwt_user_data = jwt_response.json()

        # Both should return identical user data
        assert api_key_user_data["uid"] == jwt_user_data["uid"]
        assert api_key_user_data["mail"] == jwt_user_data["mail"]
        assert api_key_user_data["name"] == jwt_user_data["name"]

    @pytest.mark.asyncio
    async def test_api_key_usage_tracking(
        self,
        db_context: TestDatabaseContext,
        client,
        test_api_key
    ):
        """Test that API key usage tracking updates last_used_at."""
        # Get initial last_used_at
        initial_last_used = test_api_key.last_used_at

        # Make request with API key
        response = client.get(
            "/api/v1/orm/users/me",
            headers={"X-API-Key": test_api_key.key}
        )

        assert response.status_code == 200

        # Check that last_used_at was updated
        updated_api_key = await db_context.api_keys.get_by_key(test_api_key.key)
        assert updated_api_key.last_used_at is not None
        assert updated_api_key.last_used_at > initial_last_used

    def test_api_key_without_jwt_fallback(
        self,
        client,
        test_api_key
    ):
        """Test API key authentication works when no JWT is provided."""
        # Make request with only API key (no Authorization header)
        response = client.get(
            "/api/v1/orm/users/me",
            headers={"X-API-Key": test_api_key.key}
        )

        assert response.status_code == 200

    def test_no_auth_headers_rejected(self, client):
        """Test that requests without any auth headers are rejected."""
        # Make request without any auth headers
        response = client.get("/api/v1/orm/users/me")

        # Should be rejected (401) since endpoint requires auth
        assert response.status_code == 401

    def test_invalid_api_key_format_rejected(self, client):
        """Test various invalid API key formats are rejected."""
        invalid_keys = [
            "missing_prefix_key",
            "fullon_ak_",  # Too short
            "",  # Empty
            "fullon_ak_invalid@chars!",  # Invalid characters
        ]

        for invalid_key in invalid_keys:
            response = client.get(
                "/api/v1/orm/users/me",
                headers={"X-API-Key": invalid_key}
            )
            assert response.status_code == 401, f"Key '{invalid_key}' should be rejected"
