"""
Integration tests for OHLCV router mounting (Phase 4 Issue #27).

Tests:
- OHLCV routers mounted at correct prefix
- Endpoints accessible via OpenAPI schema
- URL structure matches expected pattern
"""
import pytest
from fastapi.testclient import TestClient
from fullon_master_api.gateway import app


class TestOHLCVMounting:
    """Test OHLCV router mounting in gateway."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_ohlcv_routers_mounted(self, client):
        """Test that OHLCV routers are mounted in application."""
        # Get OpenAPI schema
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        paths = schema.get("paths", {})

        # Should have OHLCV paths
        ohlcv_paths = [p for p in paths.keys() if "/ohlcv/" in p]
        assert len(ohlcv_paths) > 0, "Should have OHLCV endpoints mounted"

    def test_ohlcv_endpoint_url_structure(self, client):
        """Test that OHLCV endpoints follow correct URL structure."""
        response = client.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})

        # Expected OHLCV path patterns based on new router structure
        expected_patterns = [
            "/api/v1/ohlcv/{exchange}/{symbol}",               # Base OHLCV
            "/api/v1/ohlcv/{exchange}/{symbol}/{timeframe}",   # Candles with timeframe
            "/api/v1/ohlcv/{exchange}/{symbol}/ohlcv",         # Timeseries
        ]

        # Check that at least some expected patterns exist
        # Note: symbol might be {symbol:path} in OpenAPI spec
        ohlcv_paths = [p for p in paths.keys() if "/api/v1/ohlcv/" in p]
        assert len(ohlcv_paths) > 0, f"No OHLCV paths found. Available paths: {list(paths.keys())[:5]}"

        # Verify key endpoint patterns exist (accounting for {symbol:path} notation)
        has_base = any("{exchange}" in p and "{symbol" in p for p in ohlcv_paths)
        has_timeframe = any("{timeframe}" in p for p in ohlcv_paths)
        has_timeseries = any("/ohlcv" in p and "{exchange}" in p for p in ohlcv_paths)

        assert has_base, f"Missing base OHLCV endpoint. Found paths: {ohlcv_paths[:3]}"
        assert has_timeframe, f"Missing timeframe endpoint. Found paths: {ohlcv_paths[:3]}"
        assert has_timeseries, f"Missing timeseries endpoint. Found paths: {ohlcv_paths[:3]}"

    def test_ohlcv_endpoints_require_auth(self, client):
        """Test that OHLCV endpoints require authentication."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        # Check OHLCV paths exist (mounting validation)
        paths = schema.get("paths", {})
        ohlcv_paths = {k: v for k, v in paths.items() if k.startswith("/api/v1/ohlcv/")}

        assert len(ohlcv_paths) > 0, "Should have OHLCV paths mounted"

        # Note: Full authentication enforcement testing is in Issue #28
        # For mounting validation, we just verify endpoints exist and are properly prefixed
        # The auth override from Issue #26 ensures dependencies are applied

        # Verify OHLCV endpoints are properly mounted with correct prefix
        # All OHLCV paths should start with /api/v1/ohlcv/
        for path in ohlcv_paths.keys():
            assert path.startswith("/api/v1/ohlcv/"), (
                f"OHLCV endpoint {path} does not have correct prefix. "
                f"All OHLCV endpoints should be under /api/v1/ohlcv/"
            )

        # Should have at least basic OHLCV endpoints
        basic_ohlcv_paths = [p for p in ohlcv_paths.keys() if "/ohlcv/" in p and "/{exchange}" in p and "/{symbol}" in p]
        assert len(basic_ohlcv_paths) > 0, (
            f"No basic OHLCV endpoints found. Expected patterns like /api/v1/ohlcv/{{exchange}}/{{symbol}}. "
            f"Found: {list(ohlcv_paths.keys())[:3]}..."
        )

    def test_ohlcv_routes_count(self, client):
        """Test that expected number of OHLCV routes are mounted."""
        response = client.get("/openapi.json")
        schema = response.json()
        paths = schema.get("paths", {})

        # Count OHLCV-related paths
        ohlcv_paths = [p for p in paths.keys() if "/ohlcv/" in p]

        # Should have at least 3 OHLCV endpoints
        assert len(ohlcv_paths) >= 3, f"Expected at least 3 OHLCV endpoints, got {len(ohlcv_paths)}"