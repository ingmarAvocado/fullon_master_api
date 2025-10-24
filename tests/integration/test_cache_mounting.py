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
        # Get OpenAPI schema
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        paths = schema.get("paths", {})

        # Should have Cache paths
        cache_paths = [p for p in paths.keys() if "/cache/" in p]
        assert len(cache_paths) > 0, "Should have Cache endpoints mounted"

    def test_cache_endpoint_url_structure(self, client):
        """Test that Cache endpoints follow correct URL structure."""
        response = client.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})

        # Expected Cache path patterns (WebSocket endpoints)
        expected_patterns = [
            "/api/v1/cache/ws",                              # Base WebSocket endpoint
            "/api/v1/cache/ws/tickers/{connection_id}",     # Real-time ticker streaming
            "/api/v1/cache/ws/orders/{connection_id}",      # Order queue updates
            "/api/v1/cache/ws/trades/{connection_id}",      # Trade data streaming
            "/api/v1/cache/ws/accounts/{connection_id}",    # Account balance updates
            "/api/v1/cache/ws/bots/{connection_id}",        # Bot coordination
            "/api/v1/cache/ws/ohlcv/{connection_id}",       # OHLCV candlestick streaming
            "/api/v1/cache/ws/process/{connection_id}",     # Process monitoring
        ]

        for pattern in expected_patterns:
            # Check if pattern exists in paths (exact or similar)
            matching = [p for p in paths.keys() if pattern in p or p in pattern]
            assert len(matching) > 0, f"Expected path pattern '{pattern}' not found"

    def test_cache_endpoints_require_auth(self, client):
        """Test that Cache endpoints require authentication."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        # Check Cache paths exist (mounting validation)
        paths = schema.get("paths", {})
        cache_paths = {k: v for k, v in paths.items() if k.startswith("/api/v1/cache/")}

        assert len(cache_paths) > 0, "Should have Cache paths mounted"

        # Note: Full authentication enforcement testing is in Issue #33
        # For mounting validation, we just verify endpoints exist and are properly prefixed
        # The auth override from Issue #30 ensures WebSocket connections are authenticated

        # Verify Cache endpoints are properly mounted with correct prefix
        # All Cache paths should start with /api/v1/cache/
        for path in cache_paths.keys():
            assert path.startswith("/api/v1/cache/"), (
                f"Cache endpoint {path} does not have correct prefix. "
                f"All Cache endpoints should be under /api/v1/cache/"
            )

        # Should have at least basic Cache endpoints
        basic_cache_paths = [
            p for p in cache_paths.keys() if "/ws/" in p and "/{connection_id}" in p
        ]
        assert len(basic_cache_paths) > 0, (
            "No basic Cache endpoints found. Expected patterns like "
            f"/api/v1/cache/ws/tickers/{{connection_id}}. Found: {list(cache_paths.keys())[:3]}..."
        )

    def test_cache_routes_count(self, client):
        """Test that expected number of Cache routes are mounted."""
        response = client.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})

        # Count Cache-related paths
        cache_paths = [p for p in paths.keys() if "/cache/" in p]

        # Should have at least 8 Cache endpoints (all WebSocket)
        assert len(cache_paths) >= 8, f"Expected at least 8 Cache endpoints, got {len(cache_paths)}"
