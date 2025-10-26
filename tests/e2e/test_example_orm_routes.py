"""
DEPRECATED: This E2E test pattern is deprecated.

Issues:
- Uses production database (no isolation)
- Hardcoded emails cause UniqueViolationError on re-runs
- No cleanup
- Violates project's database isolation principles

Use tests/e2e/test_run_examples.py instead, which runs actual
example scripts that follow proper isolation patterns.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Deprecated - use test_run_examples.py")

"""
End-to-end test for example_orm_routes.py.

Validates that the ORM routes example works correctly with a running server.
"""
import subprocess
import time

import httpx
import pytest
from fullon_master_api.auth.jwt import JWTHandler
from fullon_master_api.config import settings
from fullon_orm import DatabaseContext
from fullon_orm.models import User


@pytest.fixture(scope="module")
def server_process():
    """
    Start server for E2E testing.

    Yields:
        subprocess.Popen: Server process
    """
    # Start server
    process = subprocess.Popen(
        ["poetry", "run", "uvicorn", "fullon_master_api.main:app", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    time.sleep(3)

    # Verify server is running
    try:
        response = httpx.get("http://localhost:8000/health", timeout=5.0)
        assert response.status_code == 200
    except Exception as e:
        process.kill()
        raise RuntimeError(f"Server failed to start: {e}")

    yield process

    # Cleanup
    process.kill()
    process.wait()


@pytest.fixture
async def test_user_and_token():
    """
    Create test user and JWT token.

    Returns:
        tuple: (user, token)
    """
    # Create test user
    from fullon_master_api.auth.jwt import hash_password

    user = User(
        mail="e2e_test@example.com",
        name="E2E",
        lastname="Test",
        password=hash_password("testpass123"),
        f2a="",
        phone="",
        id_num="",
    )

    async with DatabaseContext() as db:
        created_user = await db.users.add_user(user)

    # Generate token
    jwt_handler = JWTHandler(settings.jwt_secret_key, settings.jwt_algorithm)
    token = jwt_handler.generate_token(
        user_id=created_user.uid, username=created_user.mail, email=created_user.mail
    )

    yield (created_user, token)

    # Note: E2E tests typically don't clean up to avoid interfering with other tests


@pytest.mark.asyncio
async def test_example_get_current_user(server_process, test_user_and_token):
    """
    Test example: GET /api/v1/orm/users/me

    Validates the example pattern for getting current user.
    """
    user, token = test_user_and_token

    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/orm/users/me", headers=headers)

        assert response.status_code == 200

        user_data = response.json()
        assert user_data["uid"] == user.uid
        assert user_data["mail"] == user.mail
        assert user_data["name"] == user.name


@pytest.mark.asyncio
async def test_example_list_users(server_process, test_user_and_token):
    """
    Test example: GET /api/v1/orm/users

    Validates the example pattern for listing users.
    """
    user, token = test_user_and_token

    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/orm/users", headers=headers)

        # May return 200 or 403 depending on permissions
        assert response.status_code in [200, 403]

        if response.status_code == 200:
            users = response.json()
            assert isinstance(users, list)


@pytest.mark.asyncio
async def test_example_list_bots(server_process, test_user_and_token):
    """
    Test example: GET /api/v1/orm/bots

    Validates the example pattern for listing bots.
    """
    user, token = test_user_and_token

    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/orm/bots", headers=headers)

        # Should return 200 with list of bots (may be empty)
        assert response.status_code == 200

        bots = response.json()
        assert isinstance(bots, list)


@pytest.mark.asyncio
async def test_example_create_bot(server_process, test_user_and_token):
    """
    Test example: POST /api/v1/orm/bots

    Validates the example pattern for creating a bot.
    """
    user, token = test_user_and_token

    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        headers = {"Authorization": f"Bearer {token}"}

        bot_data = {"name": "E2E Test Bot", "active": True, "dry_run": True}

        response = await client.post("/api/v1/orm/bots", json=bot_data, headers=headers)

        # Should return 200 or 201 with created bot
        assert response.status_code in [200, 201]

        bot = response.json()
        assert "bot_id" in bot
        assert bot["name"] == "E2E Test Bot"

        # Cleanup - delete bot
        # (depends on ORM API having delete endpoint)


@pytest.mark.asyncio
async def test_example_without_auth_fails(server_process):
    """
    Test example: Requests without auth fail with 401.

    Validates error handling in examples.
    """
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # No Authorization header
        response = await client.get("/api/v1/orm/users/me")

        assert response.status_code == 401


@pytest.mark.asyncio
async def test_example_with_invalid_token_fails(server_process):
    """
    Test example: Requests with invalid token fail with 401.

    Validates error handling in examples.
    """
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        headers = {"Authorization": "Bearer invalid_token_123"}

        response = await client.get("/api/v1/orm/users/me", headers=headers)

        assert response.status_code == 401


@pytest.mark.asyncio
async def test_run_example_script(server_process):
    """
    Test running the actual example script.

    Note: This requires the example to be runnable standalone.
    """
    # This test would run the example script directly
    # For now, we validate individual endpoints above
    pass
