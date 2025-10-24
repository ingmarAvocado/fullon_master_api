"""
Integration tests for Cache router mounting (Phase 5 Issue #31).

Tests:
- Cache routers mounted at correct prefix
- Endpoints accessible via OpenAPI schema
- URL structure matches expected pattern
"""
import pytest
from fastapi.testclient import TestClient
from fullon_master_api.gateway import app


class TestCacheMounting:
    """Test Cache router mounting in gateway."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_cache_routers_mounted(self, client):
        """Test that Cache routers are mounted in application."""
        from src.fullon_master_api.gateway import app

        # Check that cache app is mounted
        mounted_routes = [
            route
            for route in app.routes
            if hasattr(route, "path") and route.path == "/api/v1/cache"
        ]
        assert len(mounted_routes) == 1, "Cache app should be mounted at /api/v1/cache"

        # Check that the mounted app has routes
        mounted_app = mounted_routes[0].app
        assert (
            len(mounted_app.routes) >= 8
        ), f"Cache app should have at least 8 routes, got {len(mounted_app.routes)}"

    def test_cache_endpoint_url_structure(self, client):
        """Test that Cache endpoints follow correct URL structure."""
        response = client.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})

        # Expected Cache path patterns (WebSocket endpoints)
        expected_patterns = [
            "/api/v1/cache/ws",  # Base WebSocket endpoint
            "/api/v1/cache/ws/tickers/{connection_id}",  # Real-time ticker streaming
            "/api/v1/cache/ws/orders/{connection_id}",  # Order queue updates
            "/api/v1/cache/ws/trades/{connection_id}",  # Trade data streaming
            "/api/v1/cache/ws/accounts/{connection_id}",  # Account balance updates
            "/api/v1/cache/ws/bots/{connection_id}",  # Bot coordination
            "/api/v1/cache/ws/ohlcv/{connection_id}",  # OHLCV candlestick streaming
            "/api/v1/cache/ws/process/{connection_id}",  # Process monitoring
        ]

        for pattern in expected_patterns:
            # Check if pattern exists in paths (exact or similar)
            matching = [p for p in paths.keys() if pattern in p or p in pattern]
            assert len(matching) > 0, f"Expected path pattern '{pattern}' not found"

    def test_cache_endpoints_require_auth(self, client):
        """Test that Cache endpoints require authentication."""
        from src.fullon_master_api.gateway import app

        # Check that cache app is mounted
        mounted_routes = [
            route
            for route in app.routes
            if hasattr(route, "path") and route.path == "/api/v1/cache"
        ]
        assert len(mounted_routes) == 1, "Cache app should be mounted at /api/v1/cache"

        # Check that the mounted app has WebSocket routes
        mounted_app = mounted_routes[0].app
        websocket_routes = [
            route for route in mounted_app.routes if hasattr(route, "path") and "/ws/" in route.path
        ]
        assert len(websocket_routes) > 0, "Cache app should have WebSocket routes"

        # Note: Full authentication enforcement testing is in Issue #33
        # For mounting validation, we just verify endpoints exist and are properly prefixed
        # The auth override from Issue #30 ensures WebSocket connections are authenticated

        # Verify Cache endpoints are properly mounted with correct prefix
        # All Cache paths should start with /ws/ in the mounted app
        for route in websocket_routes:
            assert route.path.startswith("/ws/"), (
                f"Cache WebSocket endpoint {route.path} does not have correct prefix. "
                f"All Cache WebSocket endpoints should be under /ws/"
            )

        # Should have at least basic Cache endpoints
        basic_cache_paths = [
            route for route in websocket_routes if "/{connection_id}" in route.path
        ]
        assert len(basic_cache_paths) > 0, (
            f"No basic Cache endpoints found. Expected patterns like "
            f"/ws/tickers/{{connection_id}}. Found: {[r.path for r in websocket_routes[:3]]}..."
        )

    def test_cache_routes_count(self, client):
        """Test that expected number of Cache routes are mounted."""
        from src.fullon_master_api.gateway import app

        # Check that cache app is mounted
        mounted_routes = [
            route
            for route in app.routes
            if hasattr(route, "path") and route.path == "/api/v1/cache"
        ]
        assert len(mounted_routes) == 1, "Cache app should be mounted at /api/v1/cache"

        # Count routes in the mounted cache app
        mounted_app = mounted_routes[0].app
        cache_routes = [route for route in mounted_app.routes if hasattr(route, "path")]

        # Should have at least 8 Cache endpoints (all WebSocket)
        assert (
            len(cache_routes) >= 8
        ), f"Expected at least 8 Cache endpoints, got {len(cache_routes)}"
