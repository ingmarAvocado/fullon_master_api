"""
Integration tests for OHLCV router discovery (Phase 4 Issue #20).

Tests:
- Router discovery from fullon_ohlcv_api
- Router structure validation
- Endpoint enumeration
"""
import pytest
from fastapi import APIRouter
from fullon_master_api.gateway import MasterGateway


class TestOHLCVRouterDiscovery:
    """Test OHLCV router discovery without mounting."""

    def test_discover_ohlcv_routers_returns_list(self):
        """Test that _discover_ohlcv_routers returns a list."""
        gateway = MasterGateway()
        routers = gateway._discover_ohlcv_routers()

        assert isinstance(routers, list), "Should return list of routers"

    def test_ohlcv_routers_are_api_routers(self):
        """Test that discovered routers are APIRouter instances."""
        gateway = MasterGateway()
        routers = gateway._discover_ohlcv_routers()

        for router in routers:
            assert isinstance(router, APIRouter), (
                f"Router should be APIRouter instance, got {type(router)}"
            )

    def test_ohlcv_routers_have_routes(self):
        """Test that OHLCV routers contain route definitions."""
        gateway = MasterGateway()
        routers = gateway._discover_ohlcv_routers()

        assert len(routers) > 0, "Should discover at least one OHLCV router"

        total_routes = sum(len(router.routes) for router in routers)
        assert total_routes > 0, "OHLCV routers should have at least one route"

    def test_ohlcv_router_metadata(self):
        """Test OHLCV router metadata (prefix, tags)."""
        gateway = MasterGateway()
        routers = gateway._discover_ohlcv_routers()

        for router in routers:
            # Routers may have prefix/tags
            prefix = getattr(router, 'prefix', None)
            tags = getattr(router, 'tags', None)

            # Log for debugging
            print(f"Router: prefix={prefix}, tags={tags}, routes={len(router.routes)}")

            # At minimum, should have routes
            assert len(router.routes) > 0

    def test_ohlcv_expected_endpoints_present(self):
        """Test that expected OHLCV endpoints are present in routes."""
        gateway = MasterGateway()
        routers = gateway._discover_ohlcv_routers()

        # Collect all route paths from all routers
        all_paths = []
        for router in routers:
            for route in router.routes:
                all_paths.append(route.path)

        # Expected OHLCV endpoints (from example_ohlcv_routes.py)
        expected_patterns = [
            "ohlcv",      # Should contain OHLCV path
            # "trades",     # TODO: Add when trades endpoints are implemented
        ]

        # Check if expected patterns exist in paths
        for pattern in expected_patterns:
            matching = [p for p in all_paths if pattern in p]
            assert len(matching) > 0, (
                f"Expected '{pattern}' endpoint not found in routes: {all_paths}"
            )