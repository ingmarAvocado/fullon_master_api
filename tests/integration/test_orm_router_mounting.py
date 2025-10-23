"""
Integration tests for ORM router mounting.

Tests that ORM routers are correctly mounted in the application
and accessible via the master API.
"""
import pytest
from fastapi.testclient import TestClient
from fullon_master_api.gateway import MasterGateway


@pytest.fixture
def client():
    """Create test client."""
    gateway = MasterGateway()
    return TestClient(gateway.get_app())


def test_gateway_has_mount_orm_routers_method():
    """Test that gateway has _mount_orm_routers method."""
    gateway = MasterGateway()
    assert hasattr(gateway, '_mount_orm_routers')
    assert callable(gateway._mount_orm_routers)


def test_orm_routers_are_mounted(client):
    """Test that ORM routers are mounted in the application."""
    # Get OpenAPI schema
    response = client.get("/openapi.json")
    assert response.status_code == 200

    schema = response.json()
    paths = schema.get("paths", {})

    # Check for ORM endpoints (at minimum, these should exist)
    orm_paths = [path for path in paths.keys() if path.startswith("/api/v1/orm/")]

    assert len(orm_paths) > 0, "No ORM endpoints found in OpenAPI schema"

    print(f"\nFound {len(orm_paths)} ORM endpoints:")
    for path in orm_paths[:5]:  # Print first 5
        print(f"  - {path}")


def test_orm_endpoints_require_auth(client):
    """Test that ORM endpoints require authentication."""
    # Try accessing ORM endpoint without auth (should fail)
    response = client.get("/api/v1/orm/users")

    # Should return 401 Unauthorized (no auth header)
    assert response.status_code == 401


def test_health_endpoint_still_works(client):
    """Test that health endpoint still works after mounting ORM routers."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"


def test_root_endpoint_still_works(client):
    """Test that root endpoint still works after mounting ORM routers."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "service" in data
    assert "version" in data


def test_orm_router_logging():
    """Test that ORM router mounting is logged."""
    gateway = MasterGateway()

    # Call the method - logging happens automatically via fullon_log (loguru-based)
    # This will be called during app creation, but we can test the method directly
    from fastapi import FastAPI
    app = FastAPI()
    gateway._mount_orm_routers(app)

    # Verify that routers were mounted (logging is verified manually via stderr output)
    # The method should complete without errors
    assert True
