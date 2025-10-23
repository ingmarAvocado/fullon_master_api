"""
Shared fixtures for integration tests.
"""
import pytest
from fastapi.testclient import TestClient
from fullon_master_api.gateway import MasterGateway
from fullon_master_api.auth.jwt import JWTHandler


@pytest.fixture
def gateway():
    """Create MasterGateway instance."""
    return MasterGateway()


@pytest.fixture
def client(gateway):
    """Create test client."""
    return TestClient(gateway.get_app())


@pytest.fixture
def jwt_handler():
    """Create JWT handler for generating test tokens."""
    from fullon_master_api.config import settings
    return JWTHandler(settings.jwt_secret_key, settings.jwt_algorithm)


@pytest.fixture
def test_user():
    """Create test user data (mock - since we can't easily create real ORM instances in tests)."""
    from unittest.mock import Mock
    from fullon_orm.models import User

    # Create a mock User object (since we can't easily create real ORM instances in tests)
    mock_user = Mock(spec=User)
    mock_user.uid = 1
    mock_user.mail = "testuser@example.com"
    mock_user.name = "Test"
    mock_user.username = "testuser"
    mock_user.lastname = "User"
    return mock_user


@pytest.fixture
def valid_token(jwt_handler, test_user):
    """Create valid JWT token for test user."""
    return jwt_handler.generate_token(
        user_id=test_user.uid,
        username=test_user.username,
        email=test_user.mail
    )


@pytest.fixture
def auth_headers(valid_token):
    """Create authorization headers with valid token."""
    return {"Authorization": f"Bearer {valid_token}"}


@pytest.fixture
def invalid_token():
    """Create invalid token for testing."""
    return "invalid_token_12345"


@pytest.fixture
def invalid_auth_headers(invalid_token):
    """Create authorization headers with invalid token."""
    return {"Authorization": f"Bearer {invalid_token}"}