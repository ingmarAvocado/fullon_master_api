"""
Integration tests for ORM router discovery.

Tests the ability to import and discover routers from fullon_orm_api
without mounting them to the application.
"""
from fastapi import APIRouter
from fullon_orm_api import get_all_routers


def test_can_import_get_all_routers():
    """Test that we can import get_all_routers from fullon_orm_api."""
    # This test validates the import works
    assert callable(get_all_routers)


def test_get_all_routers_returns_list():
    """Test that get_all_routers returns a list."""
    routers = get_all_routers()
    assert isinstance(routers, list)
    assert len(routers) > 0


def test_routers_are_api_router_instances():
    """Test that all returned items are APIRouter instances."""
    routers = get_all_routers()

    for router in routers:
        assert isinstance(router, APIRouter), \
            f"Expected APIRouter, got {type(router)}"


def test_routers_have_routes():
    """Test that routers contain route definitions."""
    routers = get_all_routers()

    total_routes = 0
    for router in routers:
        routes = router.routes
        total_routes += len(routes)

    assert total_routes > 0, "ORM routers should contain at least one route"


def test_router_structure():
    """Test the structure of discovered routers."""
    routers = get_all_routers()

    # Log router structure for debugging
    for i, router in enumerate(routers):
        print(f"\nRouter {i}:")
        print(f"  Prefix: {getattr(router, 'prefix', None)}")
        print(f"  Tags: {getattr(router, 'tags', [])}")
        print(f"  Routes: {len(router.routes)}")

        for route in router.routes:
            print(f"    - {route.methods} {route.path}")
