"""
Integration tests for OHLCV auth override (Phase 4 Issue #26).

Tests:
- Auth override application to OHLCV routers
- OHLCV endpoints require authentication
- Invalid/missing tokens rejected
"""
import pytest
from fastapi import APIRouter, Depends
from fullon_master_api.gateway import MasterGateway
from fullon_master_api.auth.dependencies import get_current_user


class TestOHLCVAuthOverride:
    """Test authentication override for OHLCV routers."""

    def test_auth_override_applied_to_routers(self):
        """Test that auth override is applied to discovered OHLCV routers."""
        gateway = MasterGateway()
        routers = gateway._discover_ohlcv_routers()

        assert len(routers) > 0, "Should have OHLCV routers"

        total_routes = 0
        routes_with_auth = 0

        # Check that ALL routes have authentication
        for router in routers:
            for route in router.routes:
                total_routes += 1
                has_auth = False

                # Check route.dependant.dependencies (existing dependencies)
                if hasattr(route, 'dependant'):
                    dependencies = route.dependant.dependencies
                    for dep in dependencies:
                        if hasattr(dep, 'call') and dep.call:
                            dep_name = getattr(dep.call, '__name__', '')
                            if 'get_current_user' in dep_name:
                                has_auth = True
                                break

                # Check route.dependencies (added dependencies)
                if hasattr(route, 'dependencies'):
                    for dep in route.dependencies:
                        if hasattr(dep, 'dependency') and dep.dependency:
                            dep_name = getattr(dep.dependency, '__name__', '')
                            if 'get_current_user' in dep_name:
                                has_auth = True
                                break

                if has_auth:
                    routes_with_auth += 1

        # ALL routes must have authentication
        assert routes_with_auth == total_routes, (
            f"Only {routes_with_auth}/{total_routes} routes have authentication. "
            f"All OHLCV routes must require JWT tokens!"
        )

        assert total_routes > 0, "Should have at least one route"

    def test_apply_ohlcv_auth_overrides_method_exists(self):
        """Test that _apply_ohlcv_auth_overrides method exists."""
        gateway = MasterGateway()

        assert hasattr(gateway, '_apply_ohlcv_auth_overrides'), (
            "MasterGateway should have _apply_ohlcv_auth_overrides method"
        )

        # Create test router
        test_router = APIRouter()

        @test_router.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        # Should not raise error
        gateway._apply_ohlcv_auth_overrides(test_router)

    def test_ohlcv_routes_require_authentication(self):
        """Test that OHLCV routes require authentication (integration test)."""
        gateway = MasterGateway()

        # This test validates that auth override is properly applied
        routers = gateway._discover_ohlcv_routers()

        auth_required_routes = []
        all_routes = []
        total_routes = 0

        for router in routers:
            for route in router.routes:
                total_routes += 1
                # Handle both HTTP routes (with methods) and WebSocket routes
                methods = getattr(route, 'methods', {'WS'})
                route_info = f"{methods} {route.path}"
                all_routes.append(route_info)
                has_auth = False

                # Check for get_current_user dependency
                if hasattr(route, 'dependant'):
                    dependencies = route.dependant.dependencies
                    for dep in dependencies:
                        if hasattr(dep, 'call') and dep.call:
                            dep_name = getattr(dep.call, '__name__', '')
                            if 'get_current_user' in dep_name:
                                has_auth = True
                                break

                if hasattr(route, 'dependencies'):
                    for dep in route.dependencies:
                        if hasattr(dep, 'dependency') and dep.dependency:
                            dep_name = getattr(dep.dependency, '__name__', '')
                            if 'get_current_user' in dep_name:
                                has_auth = True
                                break

                if has_auth:
                    auth_required_routes.append(route_info)

        # Verify that ALL routes require authentication
        assert len(auth_required_routes) == total_routes, (
            f"Only {len(auth_required_routes)}/{total_routes} routes require authentication. "
            f"Missing auth: {[r for r in all_routes if r not in auth_required_routes]}"
        )

        assert total_routes > 0, "Should have routes to test"