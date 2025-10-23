"""
Shared fixtures for integration tests.

This extends the base conftest.py with integration-specific fixtures:
- Gateway and client fixtures for FastAPI testing
- JWT token generation for authenticated tests
- Real database user creation using factories
"""
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from fullon_master_api.auth.jwt import JWTHandler
from fullon_master_api.gateway import MasterGateway

# Import factories
from tests.factories import UserFactory


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


@pytest_asyncio.fixture
async def test_user(db_context, worker_id):
    """Create test user using UserFactory.

    Uses the factory pattern for clean, maintainable test data creation.
    The user is automatically rolled back after the test completes.

    Uses worker_id for parallel execution isolation.

    Returns:
        User: Persisted User model instance with uid assigned
    """
    # Worker-specific email for parallel execution
    email_suffix = f"_{worker_id}" if worker_id != "master" else ""
    email = f"testuser{email_suffix}@example.com"

    # Check if user already exists (from previous test)
    try:
        existing_user = await db_context.users.get_by_email(email)
        if existing_user:
            return existing_user
    except Exception:
        pass  # User doesn't exist, create it

    # Create user using factory with repository (commits for middleware visibility)
    user = await UserFactory.create_with_repository(
        db_context=db_context,
        email=email,
        name="Test",
        lastname="User",
        password="hashed_password_123"
    )

    return user


@pytest_asyncio.fixture
async def valid_token(jwt_handler, test_user):
    """Create valid JWT token for test user."""
    return jwt_handler.create_token({
        "sub": test_user.mail,
        "user_id": test_user.uid,
        "scopes": ["read", "write"]
    })


@pytest_asyncio.fixture
async def auth_headers(valid_token):
    """Create authorization headers with valid token."""
    return {"Authorization": f"Bearer {valid_token}"}
