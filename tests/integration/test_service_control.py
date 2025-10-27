"""
Integration tests for service control endpoints.

Tests admin-only service control API endpoints.
"""
import pytest
import pytest_asyncio


class TestServiceControlEndpoints:
    """Test service control endpoints."""

    @pytest.fixture(autouse=True, scope="function")
    async def cleanup_services(self, test_app):
        """Clean up any running services after each test."""
        yield
        # Stop all services after test
        try:
            # Get service manager from app state
            service_manager = test_app.state.service_manager
            await service_manager.stop_all()
        except Exception:
            pass  # Ignore cleanup errors

    @pytest_asyncio.fixture(scope="function", autouse=False)
    async def test_admin_user(self, db_context):
        """Create or get admin user for testing."""
        from fullon_orm.models import User
        from fullon_master_api.auth.jwt import hash_password
        from fullon_master_api.config import settings
        from sqlalchemy.exc import IntegrityError

        # Try to create admin user
        user = User(
            mail=settings.admin_mail,  # Must match settings for admin access
            name="Admin",
            lastname="User",
            password=hash_password("adminpass123"),
            f2a="",
            phone="",
            id_num="",
        )

        try:
            user = await db_context.users.add_user(user)
            return user
        except (IntegrityError, Exception) as e:
            # Admin already exists, fetch and return it
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                existing_admin = await db_context.users.get_by_email(settings.admin_mail)
                return existing_admin
            else:
                # Some other error, re-raise
                raise

    @pytest_asyncio.fixture(scope="function")
    async def test_regular_user(self, db_context):
        """Create regular user for testing with unique email."""
        import uuid
        from fullon_orm.models import User
        from fullon_master_api.auth.jwt import hash_password

        # Use unique email per test to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        user = User(
            mail=f"user_{unique_id}@example.com",
            name="Regular",
            lastname="User",
            password=hash_password("userpass123"),
            f2a="",
            phone="",
            id_num="",
        )
        user = await db_context.users.add_user(user)
        return user

    @pytest.fixture(scope="function")
    def admin_token(self, test_admin_user, jwt_handler):
        """Generate JWT token for admin user."""
        return jwt_handler.generate_token(
            user_id=test_admin_user.uid,
            username=test_admin_user.mail,
            email=test_admin_user.mail,
        )

    @pytest.fixture(scope="function")
    def user_token(self, test_regular_user, jwt_handler):
        """Generate JWT token for regular user."""
        return jwt_handler.generate_token(
            user_id=test_regular_user.uid,
            username=test_regular_user.mail,
            email=test_regular_user.mail,
        )

    @pytest_asyncio.fixture(scope="function")
    async def admin_client(self, gateway, admin_token):
        """Create async test client with admin authentication."""
        from httpx import AsyncClient, ASGITransport

        transport = ASGITransport(app=gateway.get_app())
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            client.headers.update({"Authorization": f"Bearer {admin_token}"})
            yield client

    @pytest_asyncio.fixture(scope="function")
    async def user_client(self, gateway, user_token):
        """Create async test client with regular user authentication."""
        from httpx import AsyncClient, ASGITransport

        transport = ASGITransport(app=gateway.get_app())
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            client.headers.update({"Authorization": f"Bearer {user_token}"})
            yield client

    @pytest.mark.asyncio
    async def test_start_service_admin_success(self, admin_client):
        """Test admin can start a service."""
        service_name = "ticker"

        response = await admin_client.post(f"/api/v1/services/{service_name}/start")

        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.content}")
        if response.status_code != 200:
            print(f"Response JSON: {response.json()}")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == service_name
        assert data["status"] == "started"

        # Clean up: stop the service we started
        stop_response = await admin_client.post(f"/api/v1/services/{service_name}/stop")
        assert stop_response.status_code == 200

    @pytest.mark.asyncio
    async def test_stop_service_admin_success(self, admin_client):
        """Test admin can stop a service."""
        service_name = "ticker"

        # Start service first
        start_response = await admin_client.post(f"/api/v1/services/{service_name}/start")
        assert start_response.status_code == 200

        # Stop service
        stop_response = await admin_client.post(f"/api/v1/services/{service_name}/stop")

        assert stop_response.status_code == 200
        data = stop_response.json()
        assert data["service"] == service_name
        assert data["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_restart_service_admin_success(self, admin_client):
        """Test admin can restart a service."""
        service_name = "ticker"

        response = await admin_client.post(f"/api/v1/services/{service_name}/restart")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == service_name
        assert data["status"] == "restarted"

    @pytest.mark.asyncio
    async def test_get_service_status_admin_success(self, admin_client):
        """Test admin can get service status."""
        service_name = "ticker"

        response = await admin_client.get(f"/api/v1/services/{service_name}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == service_name
        assert data["status"] in ["running", "stopped"]
        assert "is_running" in data

    @pytest.mark.asyncio
    async def test_get_all_services_status_admin_success(self, admin_client):
        """Test admin can get all services status."""

        response = await admin_client.get("/api/v1/services")

        assert response.status_code == 200
        data = response.json()
        assert "services" in data

        services = data["services"]
        assert len(services) == 4

        for service_name in ["ticker", "ohlcv", "account", "health_monitor"]:
            assert service_name in services
            service_data = services[service_name]
            assert service_data["status"] in ["running", "stopped"]
            assert "is_running" in service_data

    @pytest.mark.asyncio
    async def test_start_service_non_admin_forbidden(self, user_client):
        """Test non-admin user cannot start services."""
        service_name = "ticker"

        response = await user_client.post(f"/api/v1/services/{service_name}/start")

        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_stop_service_non_admin_forbidden(self, user_client):
        """Test non-admin user cannot stop services."""
        service_name = "ticker"

        response = await user_client.post(f"/api/v1/services/{service_name}/stop")

        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_restart_service_non_admin_forbidden(self, user_client):
        """Test non-admin user cannot restart services."""
        service_name = "ticker"

        response = await user_client.post(f"/api/v1/services/{service_name}/restart")

        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_service_status_non_admin_forbidden(self, user_client):
        """Test non-admin user cannot get service status."""
        service_name = "ticker"

        response = await user_client.get(f"/api/v1/services/{service_name}/status")

        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_all_services_status_non_admin_forbidden(self, user_client):
        """Test non-admin user cannot get all services status."""

        response = await user_client.get("/api/v1/services")

        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_start_service_already_running(self, admin_client):
        """Test starting a service that's already running returns 400."""
        service_name = "ticker"

        # Start service first
        start_response = await admin_client.post(f"/api/v1/services/{service_name}/start")
        assert start_response.status_code == 200

        # Try to start again
        second_start_response = await admin_client.post(f"/api/v1/services/{service_name}/start")

        assert second_start_response.status_code == 400
        assert "is already running" in second_start_response.json()["detail"]

        # Clean up: stop the service
        stop_response = await admin_client.post(f"/api/v1/services/{service_name}/stop")
        assert stop_response.status_code == 200

    @pytest.mark.asyncio
    async def test_stop_service_not_running(self, admin_client):
        """Test stopping a service that's not running returns 400."""
        service_name = "ticker"

        response = await admin_client.post(f"/api/v1/services/{service_name}/stop")

        assert response.status_code == 400
        assert "is not running" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_invalid_service_name(self, admin_client):
        """Test invalid service name returns 422."""

        response = await admin_client.post("/api/v1/services/invalid_service/start")

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_service_lifecycle_workflow(self, admin_client):
        """Test complete service lifecycle workflow."""
        service_name = "ohlcv"

        # 1. Check initial status (should be stopped)
        response = await admin_client.get(f"/api/v1/services/{service_name}/status")
        assert response.status_code == 200
        assert response.json()["status"] == "stopped"

        # 2. Start service
        response = await admin_client.post(f"/api/v1/services/{service_name}/start")
        assert response.status_code == 200
        assert response.json()["status"] == "started"

        # 3. Check status (should be running)
        response = await admin_client.get(f"/api/v1/services/{service_name}/status")
        assert response.status_code == 200
        assert response.json()["status"] == "running"

        # 4. Restart service
        response = await admin_client.post(f"/api/v1/services/{service_name}/restart")
        assert response.status_code == 200
        assert response.json()["status"] == "restarted"

        # 5. Stop service
        response = await admin_client.post(f"/api/v1/services/{service_name}/stop")
        assert response.status_code == 200
        assert response.json()["status"] == "stopped"

        # 6. Check final status (should be stopped)
        response = await admin_client.get(f"/api/v1/services/{service_name}/status")
        assert response.status_code == 200
        assert response.json()["status"] == "stopped"
